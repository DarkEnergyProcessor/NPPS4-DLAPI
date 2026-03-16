import type {
  Env,
  SyncCursor,
  SyncFileLink,
  PublicInfoModel,
  DownloadUpdateModel,
  BatchDownloadInfoModel,
  FileDataV2,
} from "./types";
import { PLATFORM_MAP } from "./types";

const SYNC_CURSOR_KEY = "sync:cursor";
const FILES_PER_RUN = 10;
const PACKAGE_TYPES = [0, 1, 2, 3, 4, 5, 6] as const;

function emptyCursor(): SyncCursor {
  return {
    phase: "fetch_links",
    upstreamVersion: "",
    files: [],
    fileIndex: 0,
    bytesUploaded: 0,
    filesUploaded: 0,
    totalBytes: 0,
    totalFiles: 0,
    startedAt: Date.now(),
    lastActivityAt: Date.now(),
    metadataWrites: [],
  };
}

async function loadCursor(kv: KVNamespace): Promise<SyncCursor | null> {
  const raw = await kv.get(SYNC_CURSOR_KEY, "text");
  if (!raw) return null;
  return JSON.parse(raw) as SyncCursor;
}

async function saveCursor(kv: KVNamespace, cursor: SyncCursor): Promise<void> {
  cursor.lastActivityAt = Date.now();
  await kv.put(SYNC_CURSOR_KEY, JSON.stringify(cursor));
}

export async function clearCursor(kv: KVNamespace): Promise<void> {
  await kv.delete(SYNC_CURSOR_KEY);
}

/** Call the upstream DLAPI. Mirrors clone.py's HTTP behavior. */
async function upstreamApi<T>(env: Env, endpoint: string, body?: unknown): Promise<T> {
  const base = env.UPSTREAM_URL!.replace(/\/+$/, "");
  const url = `${base}/${endpoint}`;
  const headers: Record<string, string> = {};

  if (env.UPSTREAM_SHARED_KEY) {
    headers["DLAPI-Shared-Key"] = encodeURIComponent(env.UPSTREAM_SHARED_KEY);
  }

  const init: RequestInit = { headers };
  if (body !== undefined) {
    init.method = "POST";
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const resp = await fetch(url, init);
  if (!resp.ok) {
    throw new Error(`Upstream ${endpoint}: HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

/** Download a file from the upstream, verify checksums, upload to R2. */
async function downloadAndUpload(
  env: Env,
  link: SyncFileLink
): Promise<boolean> {
  // Skip if already in R2
  const existing = await env.ARCHIVE_BUCKET.head(link.r2Key);
  if (existing !== null && existing.size === link.size) {
    return false; // already uploaded
  }

  const resp = await fetch(link.url);
  if (!resp.ok) {
    throw new Error(`Download ${link.url}: HTTP ${resp.status}`);
  }

  const data = await resp.arrayBuffer();

  // Verify checksums
  const md5Buf = await crypto.subtle.digest("MD5", data);
  const sha256Buf = await crypto.subtle.digest("SHA-256", data);
  const md5Hex = hexEncode(md5Buf);
  const sha256Hex = hexEncode(sha256Buf);

  if (md5Hex !== link.md5) {
    throw new Error(`MD5 mismatch for ${link.r2Key}: expected ${link.md5}, got ${md5Hex}`);
  }
  if (sha256Hex !== link.sha256) {
    throw new Error(`SHA256 mismatch for ${link.r2Key}: expected ${link.sha256}, got ${sha256Hex}`);
  }

  await env.ARCHIVE_BUCKET.put(link.r2Key, data);
  return true;
}

function hexEncode(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Phase 1: Fetch all links from the upstream API and build the complete
 * file manifest + metadata list. This is lightweight (API calls only).
 */
async function fetchAllLinks(env: Env, cursor: SyncCursor): Promise<void> {
  const info = await upstreamApi<PublicInfoModel>(env, "api/publicinfo");
  cursor.upstreamVersion = info.gameVersion;

  const files: SyncFileLink[] = [];
  const metadataWrites: Array<{ key: string; data: unknown }> = [];

  for (let platIdx = 0; platIdx < PLATFORM_MAP.length; platIdx++) {
    const platId = platIdx + 1; // 1-indexed for API
    const platDir = PLATFORM_MAP[platIdx];

    // ── Updates ──
    const updates = await upstreamApi<DownloadUpdateModel[]>(env, "api/v1/update", {
      version: "1.0",
      platform: platId,
    });

    // Group updates by version for infov2.json metadata
    const updatesByVersion = new Map<string, FileDataV2[]>();
    const updateVersions: string[] = [];

    for (const u of updates) {
      const fileName = u.url.split("/").pop()!;
      const verPath = `${platDir}/update/${u.version}`;

      files.push({
        url: u.url,
        r2Key: `${verPath}/${fileName}`,
        size: u.size,
        md5: u.checksums.md5,
        sha256: u.checksums.sha256,
      });

      if (!updatesByVersion.has(u.version)) {
        updatesByVersion.set(u.version, []);
        updateVersions.push(u.version);
      }
      updatesByVersion.get(u.version)!.push({
        name: fileName,
        size: u.size,
        md5: u.checksums.md5,
        sha256: u.checksums.sha256,
      });
    }

    // Write update metadata
    metadataWrites.push({
      key: `${platDir}/update/infov2.json`,
      data: updateVersions,
    });
    for (const [ver, fds] of updatesByVersion) {
      metadataWrites.push({
        key: `${platDir}/update/${ver}/infov2.json`,
        data: fds,
      });
    }

    // ── Packages ──
    const packageVersions: string[] = [cursor.upstreamVersion];
    metadataWrites.push({
      key: `${platDir}/package/info.json`,
      data: packageVersions,
    });

    for (const pkgType of PACKAGE_TYPES) {
      const batch = await upstreamApi<BatchDownloadInfoModel[]>(env, "api/v1/batch", {
        package_type: pkgType,
        platform: platId,
        exclude: [],
      });

      if (!Array.isArray(batch) || batch.length === 0) continue;

      // Group by packageId
      const byPkgId = new Map<number, FileDataV2[]>();
      const pkgIds: number[] = [];

      for (const b of batch) {
        const fileName = b.url.split("/").pop()!;
        const pkgPath = `${platDir}/package/${cursor.upstreamVersion}/${pkgType}/${b.packageId}`;

        files.push({
          url: b.url,
          r2Key: `${pkgPath}/${fileName}`,
          size: b.size,
          md5: b.checksums.md5,
          sha256: b.checksums.sha256,
        });

        if (!byPkgId.has(b.packageId)) {
          byPkgId.set(b.packageId, []);
          pkgIds.push(b.packageId);
        }
        byPkgId.get(b.packageId)!.push({
          name: fileName,
          size: b.size,
          md5: b.checksums.md5,
          sha256: b.checksums.sha256,
        });
      }

      // Package type info.json (list of IDs)
      metadataWrites.push({
        key: `${platDir}/package/${cursor.upstreamVersion}/${pkgType}/info.json`,
        data: pkgIds.sort((a, b) => a - b),
      });

      // Per-package infov2.json
      for (const [pkgId, fds] of byPkgId) {
        metadataWrites.push({
          key: `${platDir}/package/${cursor.upstreamVersion}/${pkgType}/${pkgId}/infov2.json`,
          data: fds,
        });
      }
    }
  }

  // Release info
  const releaseInfo = await upstreamApi<Record<string, string>>(env, "api/v1/release_info");
  metadataWrites.push({ key: "release_info.json", data: releaseInfo });

  // Generation marker
  metadataWrites.push({ key: "generation.json", data: { major: 1, minor: 1 } });

  cursor.files = files;
  cursor.totalFiles = files.length;
  cursor.totalBytes = files.reduce((sum, f) => sum + f.size, 0);
  cursor.metadataWrites = metadataWrites;
  cursor.phase = "update";
}

/**
 * Phase 2+3: Download files and upload to R2, bounded by FILES_PER_RUN.
 * Updates and packages are in one flat list — no distinction needed.
 */
async function syncFiles(env: Env, cursor: SyncCursor): Promise<void> {
  let processed = 0;

  while (cursor.fileIndex < cursor.files.length && processed < FILES_PER_RUN) {
    const link = cursor.files[cursor.fileIndex];
    try {
      const uploaded = await downloadAndUpload(env, link);
      if (uploaded) {
        cursor.bytesUploaded += link.size;
      }
      cursor.filesUploaded++;
      cursor.fileIndex++;
      processed++;
      cursor.lastError = undefined;
    } catch (err) {
      cursor.lastError = err instanceof Error ? err.message : String(err);
      // Save progress and bail — next invocation will retry this file
      return;
    }
  }

  if (cursor.fileIndex >= cursor.files.length) {
    cursor.phase = "metadata";
  }
}

/** Phase 4: Write all metadata JSON files to R2. */
async function writeMetadata(env: Env, cursor: SyncCursor): Promise<void> {
  for (const { key, data } of cursor.metadataWrites) {
    await env.ARCHIVE_BUCKET.put(key, JSON.stringify(data), {
      httpMetadata: { contentType: "application/json" },
    });
  }
  cursor.phase = "done";
}

/** Main entry point — called by the scheduled() handler. */
export async function runSync(env: Env): Promise<void> {
  if (!env.UPSTREAM_URL) return;

  let cursor = await loadCursor(env.SYNC_KV);

  // If previous sync completed, check if upstream version changed
  if (cursor && cursor.phase === "done") {
    const info = await upstreamApi<PublicInfoModel>(env, "api/publicinfo");
    if (info.gameVersion === cursor.upstreamVersion) {
      return; // already synced to latest
    }
    // New version available — start fresh
    cursor = null;
  }

  if (!cursor) {
    cursor = emptyCursor();
  }

  switch (cursor.phase) {
    case "fetch_links":
      await fetchAllLinks(env, cursor);
      // Save and let the next invocation start downloading
      break;
    case "update":
    case "packages":
      await syncFiles(env, cursor);
      break;
    case "metadata":
      await writeMetadata(env, cursor);
      break;
  }

  await saveCursor(env.SYNC_KV, cursor);
}

/** Get current sync status for the dashboard. */
export async function getSyncStatus(kv: KVNamespace): Promise<SyncCursor | null> {
  return loadCursor(kv);
}
