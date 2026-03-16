import { describe, it, expect, beforeAll } from "vitest";
import { env, SELF } from "cloudflare:test";
import { getSyncStatus, clearCursor } from "../src/sync";
import { seedBucket } from "./fixtures";

beforeAll(async () => {
  await seedBucket(env.ARCHIVE_BUCKET);
});

describe("Sync cursor management", () => {
  it("returns null when no sync has been started", async () => {
    await clearCursor(env.SYNC_KV);
    const status = await getSyncStatus(env.SYNC_KV);
    expect(status).toBeNull();
  });

  it("does not run when UPSTREAM_URL is not set", async () => {
    // Import runSync and call it with env that has no UPSTREAM_URL
    const { runSync } = await import("../src/sync");
    await runSync(env as any);
    const status = await getSyncStatus(env.SYNC_KV);
    expect(status).toBeNull();
  });
});

describe("Dashboard", () => {
  it("returns HTML dashboard at /dashboard when no sync is active", async () => {
    await clearCursor(env.SYNC_KV);
    const res = await SELF.fetch("http://localhost/dashboard");
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toContain("text/html");
    const html = await res.text();
    expect(html).toContain("Sync Dashboard");
    expect(html).toContain("No sync in progress");
  });

  it("returns JSON status at /dashboard/json when no sync is active", async () => {
    await clearCursor(env.SYNC_KV);
    const res = await SELF.fetch("http://localhost/dashboard/json");
    expect(res.status).toBe(200);
    const data: any = await res.json();
    expect(data.status).toBe("idle");
  });

  it("shows progress when sync cursor exists in KV", async () => {
    // Manually write a cursor to KV to simulate an in-progress sync
    const fakeCursor = {
      phase: "update",
      upstreamVersion: "59.4",
      files: [],
      fileIndex: 5,
      bytesUploaded: 1024 * 1024 * 500,
      filesUploaded: 5,
      totalBytes: 1024 * 1024 * 1024 * 32,
      totalFiles: 23071,
      startedAt: Date.now() - 3600000,
      lastActivityAt: Date.now() - 60000,
      metadataWrites: [],
    };
    await env.SYNC_KV.put("sync:cursor", JSON.stringify(fakeCursor));

    const res = await SELF.fetch("http://localhost/dashboard");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Downloading files");
    expect(html).toContain("59.4");
    expect(html).toContain("23,071");

    const jsonRes = await SELF.fetch("http://localhost/dashboard/json");
    const data: any = await jsonRes.json();
    expect(data.status).toBe("update");
    expect(data.upstreamVersion).toBe("59.4");
    expect(data.totalFiles).toBe(23071);
    expect(data.filesUploaded).toBe(5);
    expect(data.progressPercent).toBeGreaterThan(0);

    // Clean up
    await clearCursor(env.SYNC_KV);
  });

  it("shows error state on dashboard", async () => {
    const fakeCursor = {
      phase: "update",
      upstreamVersion: "59.4",
      files: [],
      fileIndex: 3,
      bytesUploaded: 100,
      filesUploaded: 3,
      totalBytes: 1000,
      totalFiles: 10,
      startedAt: Date.now() - 60000,
      lastActivityAt: Date.now() - 30000,
      metadataWrites: [],
      lastError: "Download failed: HTTP 503",
    };
    await env.SYNC_KV.put("sync:cursor", JSON.stringify(fakeCursor));

    const res = await SELF.fetch("http://localhost/dashboard");
    const html = await res.text();
    expect(html).toContain("Download failed: HTTP 503");
    expect(html).toContain("Will retry");

    const jsonRes = await SELF.fetch("http://localhost/dashboard/json");
    const data: any = await jsonRes.json();
    expect(data.lastError).toBe("Download failed: HTTP 503");

    await clearCursor(env.SYNC_KV);
  });

  it("shows done state on dashboard", async () => {
    const fakeCursor = {
      phase: "done",
      upstreamVersion: "59.4",
      files: [],
      fileIndex: 100,
      bytesUploaded: 1000,
      filesUploaded: 100,
      totalBytes: 1000,
      totalFiles: 100,
      startedAt: Date.now() - 7200000,
      lastActivityAt: Date.now() - 300000,
      metadataWrites: [],
    };
    await env.SYNC_KV.put("sync:cursor", JSON.stringify(fakeCursor));

    const res = await SELF.fetch("http://localhost/dashboard");
    const html = await res.text();
    expect(html).toContain("Sync complete");

    const jsonRes = await SELF.fetch("http://localhost/dashboard/json");
    const data: any = await jsonRes.json();
    expect(data.status).toBe("done");
    expect(data.progressPercent).toBe(100);

    await clearCursor(env.SYNC_KV);
  });
});
