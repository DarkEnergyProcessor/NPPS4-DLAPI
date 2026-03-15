// Copyright (c) 2023 Dark Energy Processor
//
// This software is provided 'as-is', without any express or implied
// warranty. In no event will the authors be held liable for any damages
// arising from the use of this software.
//
// Permission is granted to anyone to use this software for any purpose,
// including commercial applications, and to alter it and redistribute it
// freely, subject to the following restrictions:
//
// 1. The origin of this software must not be misrepresented; you must not
//    claim that you wrote the original software. If you use this software
//    in a product, an acknowledgment in the product documentation would be
//    appreciated but is not required.
// 2. Altered source versions must be plainly marked as such, and must not be
//    misrepresented as being the original software.
// 3. This notice may not be removed or altered from any source distribution.

import type {
  Env,
  DownloadUpdateModel,
  BatchDownloadInfoModel,
  DownloadInfoModel,
  FileDataV2,
  MicroDlInfo,
} from "./types";
import { PLATFORM_MAP } from "./types";

async function readJson<T>(bucket: R2Bucket, key: string): Promise<T | null> {
  const obj = await bucket.get(key);
  if (obj === null) return null;
  return obj.json<T>();
}

function parseSifVersion(ver: string): [number, number] {
  const [major, minor] = ver.split(".", 2);
  return [parseInt(major, 10), parseInt(minor, 10)];
}

function versionString(ver: [number, number]): string {
  return `${ver[0]}.${ver[1]}`;
}

function compareVersions(a: [number, number], b: [number, number]): number {
  if (a[0] !== b[0]) return a[0] - b[0];
  return a[1] - b[1];
}

/**
 * Natural sort comparison for version strings.
 */
function naturalSortCompare(a: string, b: string): number {
  const ax = a.split(/(\d+)/);
  const bx = b.split(/(\d+)/);
  for (let i = 0; i < Math.max(ax.length, bx.length); i++) {
    const ai = ax[i] ?? "";
    const bi = bx[i] ?? "";
    const an = parseInt(ai, 10);
    const bn = parseInt(bi, 10);
    if (!isNaN(an) && !isNaN(bn)) {
      if (an !== bn) return an - bn;
    } else {
      if (ai < bi) return -1;
      if (ai > bi) return 1;
    }
  }
  return 0;
}

async function detectPlatformPreference(bucket: R2Bucket): Promise<number> {
  for (let i = 0; i < PLATFORM_MAP.length; i++) {
    const obj = await bucket.head(`${PLATFORM_MAP[i]}/package/info.json`);
    if (obj !== null) return i;
  }
  throw new Error("No package found!");
}

export async function getLatestVersion(bucket: R2Bucket): Promise<[number, number]> {
  const preference = await detectPlatformPreference(bucket);
  const versions = await readJson<string[]>(bucket, `${PLATFORM_MAP[preference]}/package/info.json`);
  if (!versions || versions.length === 0) throw new Error("No package found!");
  const sorted = [...versions].sort(naturalSortCompare);
  return parseSifVersion(sorted[sorted.length - 1]);
}

export async function getReleaseInfo(bucket: R2Bucket): Promise<Record<string, string>> {
  const info = await readJson<Record<string, string>>(bucket, "release_info.json");
  return info ?? {};
}

export async function getUpdateFile(
  env: Env,
  baseUrl: string,
  oldClientVersion: string,
  platform: number
): Promise<DownloadUpdateModel[]> {
  const bucket = env.ARCHIVE_BUCKET;
  const platDir = PLATFORM_MAP[platform - 1];
  const updatePath = `${platDir}/update`;
  const currentVersion = parseSifVersion(oldClientVersion);

  const versionsRaw = await readJson<string[]>(bucket, `${updatePath}/infov2.json`);
  if (!versionsRaw || versionsRaw.length === 0) return [];

  const updates: [number, number][] = [];
  for (const v of versionsRaw) {
    try {
      updates.push(parseSifVersion(v));
    } catch {
      // skip invalid
    }
  }
  updates.sort(compareVersions);

  if (updates.length === 0) return [];
  if (compareVersions(currentVersion, updates[updates.length - 1]) === 0) return [];

  const downloadData: DownloadUpdateModel[] = [];
  for (const ver of updates) {
    if (compareVersions(ver, currentVersion) <= 0) continue;
    const verStr = versionString(ver);
    const verPath = `${updatePath}/${verStr}`;
    const fileDatas = await readJson<FileDataV2[]>(bucket, `${verPath}/infov2.json`);
    if (!fileDatas) continue;

    for (const fd of fileDatas) {
      downloadData.push({
        url: `${baseUrl}/${verPath}/${fd.name}`,
        size: fd.size,
        checksums: { md5: fd.md5, sha256: fd.sha256 },
        version: verStr,
      });
    }
  }

  return downloadData;
}

export async function getBatchList(
  env: Env,
  baseUrl: string,
  pkgtype: number,
  platform: number,
  exclude: number[]
): Promise<BatchDownloadInfoModel[] | null> {
  const bucket = env.ARCHIVE_BUCKET;
  const latest = await getLatestVersion(bucket);
  const path = `${PLATFORM_MAP[platform - 1]}/package/${versionString(latest)}/${pkgtype}`;

  const packages = await readJson<number[]>(bucket, `${path}/info.json`);
  if (packages === null) return null;

  const excludeSet = new Set(exclude);
  const sortedIds = [...new Set(packages)].filter((id) => !excludeSet.has(id)).sort((a, b) => a - b);

  const result: BatchDownloadInfoModel[] = [];
  for (const pkgid of sortedIds) {
    const fileDatas = await readJson<FileDataV2[]>(bucket, `${path}/${pkgid}/infov2.json`);
    if (!fileDatas) continue;

    for (const fd of fileDatas) {
      result.push({
        url: `${baseUrl}/${path}/${pkgid}/${fd.name}`,
        size: fd.size,
        checksums: { md5: fd.md5, sha256: fd.sha256 },
        packageId: pkgid,
      });
    }
  }

  return result;
}

export async function getSinglePackage(
  env: Env,
  baseUrl: string,
  pkgtype: number,
  pkgid: number,
  platform: number
): Promise<DownloadInfoModel[] | null> {
  const bucket = env.ARCHIVE_BUCKET;
  const latest = await getLatestVersion(bucket);
  const path = `${PLATFORM_MAP[platform - 1]}/package/${versionString(latest)}/${pkgtype}/${pkgid}`;

  const fileDatas = await readJson<FileDataV2[]>(bucket, `${path}/infov2.json`);
  if (fileDatas === null) return null;

  return fileDatas.map((fd) => ({
    url: `${baseUrl}/${path}/${fd.name}`,
    size: fd.size,
    checksums: { md5: fd.md5, sha256: fd.sha256 },
  }));
}

export async function getDatabaseFile(env: Env, name: string): Promise<ArrayBuffer | null> {
  const bucket = env.ARCHIVE_BUCKET;
  const preference = await detectPlatformPreference(bucket);
  const latest = await getLatestVersion(bucket);
  // Sanitize: only allow alphanumeric and underscore
  const dbname = name.replace(/[^a-zA-Z0-9_]/g, "");
  const path = `${PLATFORM_MAP[preference]}/package/${versionString(latest)}/db/${dbname}.db_`;

  const obj = await bucket.get(path);
  if (obj === null) return null;
  return obj.arrayBuffer();
}

export async function getMicroDlFile(
  env: Env,
  baseUrl: string,
  file: string,
  platform: number
): Promise<DownloadInfoModel> {
  const bucket = env.ARCHIVE_BUCKET;
  const latest = await getLatestVersion(bucket);
  const commonPath = `${PLATFORM_MAP[platform - 1]}/package/${versionString(latest)}/microdl`;

  const microDlMap = await readJson<MicroDlInfo>(bucket, `${commonPath}/info.json`);

  // Normalize path: remove "..", normalize separators, strip leading slash
  let sanitized = file.replace(/\.\./g, "").replace(/\\/g, "/");
  // Collapse multiple slashes
  sanitized = sanitized.replace(/\/+/g, "/");
  if (sanitized.startsWith("/")) sanitized = sanitized.slice(1);

  const path = `${commonPath}/${sanitized}`;

  const result: DownloadInfoModel = {
    url: `${baseUrl}/${path}`,
    size: 0,
    checksums: {
      md5: "d41d8cd98f00b204e9800998ecf8427e",
      sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
  };

  if (microDlMap && sanitized in microDlMap) {
    const info = microDlMap[sanitized];
    result.size = info.size;
    result.checksums.md5 = info.md5;
    result.checksums.sha256 = info.sha256;
  }

  return result;
}
