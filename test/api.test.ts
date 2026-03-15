import { describe, it, expect, beforeAll } from "vitest";
import { env, SELF } from "cloudflare:test";
import { seedBucket } from "./fixtures";

const BASE = "http://localhost";

beforeAll(async () => {
  await seedBucket(env.ARCHIVE_BUCKET);
});

// ─── /api/publicinfo ───

describe("GET /api/publicinfo", () => {
  it("returns server information", async () => {
    const res = await SELF.fetch(`${BASE}/api/publicinfo`);
    expect(res.status).toBe(200);
    const data = await res.json();

    expect(data.publicApi).toBe(true);
    expect(data.dlapiVersion).toEqual({ major: 1, minor: 1 });
    expect(data.serveTimeLimit).toBe(0);
    // Latest version from iOS/package/info.json -> ["59.4"]
    expect(data.gameVersion).toBe("59.4");
    expect(data.application).toBeDefined();
    expect(data.application.NPPS4DLAPIVersion).toBe("2023.05.14");
  });
});

// ─── /api/v1/update ───

describe("POST /api/v1/update", () => {
  it("returns update files when behind latest (iOS)", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version: "59.0", platform: 1 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    // Should get updates for 59.2 and 59.4
    expect(data.length).toBe(2);

    // First update: 59.2
    expect(data[0].version).toBe("59.2");
    expect(data[0].size).toBe(15);
    expect(data[0].checksums.md5).toBe("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1");
    expect(data[0].url).toContain("/archive/iOS/update/59.2/1.zip");

    // Second update: 59.4
    expect(data[1].version).toBe("59.4");
    expect(data[1].size).toBe(15);
    expect(data[1].url).toContain("/archive/iOS/update/59.4/1.zip");
  });

  it("returns empty array when already at latest", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version: "59.4", platform: 1 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();
    expect(data).toEqual([]);
  });

  it("returns only newer updates (partial)", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version: "59.2", platform: 1 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    // Only 59.4 should be returned (59.2 is current, not newer)
    expect(data.length).toBe(1);
    expect(data[0].version).toBe("59.4");
  });

  it("works for Android platform", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version: "59.0", platform: 2 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    expect(data.length).toBe(1);
    expect(data[0].version).toBe("59.4");
    expect(data[0].size).toBe(250);
    expect(data[0].url).toContain("/archive/Android/update/59.4/1.zip");
  });
});

// ─── /api/v1/batch ───

describe("POST /api/v1/batch", () => {
  it("returns all packages for a type (iOS bootstrap)", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 0, platform: 1, exclude: [] }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    // Package IDs 1 and 2. ID 2 has 2 files, so total = 3
    expect(data.length).toBe(3);

    // Check packageId 1
    const pkg1 = data.filter((d: any) => d.packageId === 1);
    expect(pkg1.length).toBe(1);
    expect(pkg1[0].size).toBe(300);
    expect(pkg1[0].url).toContain("/archive/iOS/package/59.4/0/1/1.zip");

    // Check packageId 2 (has 2 files)
    const pkg2 = data.filter((d: any) => d.packageId === 2);
    expect(pkg2.length).toBe(2);
  });

  it("excludes specified package IDs", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 0, platform: 1, exclude: [2] }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    // Only package 1 should remain
    expect(data.length).toBe(1);
    expect(data[0].packageId).toBe(1);
  });

  it("returns 404 for non-existent package type", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 3, platform: 1, exclude: [] }),
    });
    expect(res.status).toBe(404);
    const data = await res.json();
    expect(data.detail).toBe("Package type not found");
  });

  it("defaults exclude to empty array when omitted", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 0, platform: 1 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();
    expect(data.length).toBe(3);
  });
});

// ─── /api/v1/download ───

describe("POST /api/v1/download", () => {
  it("returns files for a specific package", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 0, package_id: 2, platform: 1 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    // Package 0/2 has 2 files
    expect(data.length).toBe(2);
    expect(data[0].size).toBe(400);
    expect(data[0].checksums.md5).toBe("cccccccccccccccccccccccccccccc02");
    expect(data[0].url).toContain("/archive/iOS/package/59.4/0/2/1.zip");
    expect(data[1].size).toBe(350);
    expect(data[1].url).toContain("/archive/iOS/package/59.4/0/2/2.zip");
  });

  it("returns 404 for non-existent package ID", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 0, package_id: 999, platform: 1 }),
    });
    expect(res.status).toBe(404);
    const data = await res.json();
    expect(data.detail).toBe("Package not found");
  });

  it("works for Android platform", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 0, package_id: 1, platform: 2 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();
    expect(data.length).toBe(1);
    expect(data[0].size).toBe(320);
    expect(data[0].url).toContain("/archive/Android/package/59.4/0/1/1.zip");
  });
});

// ─── /api/v1/getdb ───

describe("GET /api/v1/getdb/:name", () => {
  it("returns decrypted database file", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/getdb/testdb`);
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/vnd.sqlite3");
    expect(res.headers.get("Content-Disposition")).toBe('attachment; filename="testdb.db_"');

    const body = await res.text();
    expect(body).toBe("FAKE-SQLITE3-DATA");
  });

  it("returns 404 for non-existent database", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/getdb/nonexistent`);
    expect(res.status).toBe(404);
    const data = await res.json();
    expect(data.detail).toBe("Database not found");
  });

  it("sanitizes database name (strips non-alphanumeric)", async () => {
    // "test..db" should be sanitized to "testdb" (dots stripped)
    const res = await SELF.fetch(`${BASE}/api/v1/getdb/test..db`);
    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toBe("FAKE-SQLITE3-DATA");
  });
});

// ─── /api/v1/getfile ───

describe("POST /api/v1/getfile", () => {
  it("returns download info for micro files", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/getfile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files: ["some/file.txt"], platform: 1 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    expect(data.length).toBe(1);
    expect(data[0].size).toBe(50);
    expect(data[0].checksums.md5).toBe("11111111111111111111111111111111");
    expect(data[0].checksums.sha256).toBe("2222222222222222222222222222222222222222222222222222222222222222");
    expect(data[0].url).toContain("/archive/iOS/package/59.4/microdl/some/file.txt");
  });

  it("returns multiple files", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/getfile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        files: ["some/file.txt", "another/asset.png"],
        platform: 1,
      }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    expect(data.length).toBe(2);
    expect(data[0].size).toBe(50);
    expect(data[1].size).toBe(1024);
    expect(data[1].checksums.md5).toBe("33333333333333333333333333333333");
  });

  it("returns empty checksums for unknown files", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/getfile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files: ["nonexistent/file.bin"], platform: 1 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    expect(data.length).toBe(1);
    expect(data[0].size).toBe(0);
    // Empty file checksums (as per original implementation)
    expect(data[0].checksums.md5).toBe("d41d8cd98f00b204e9800998ecf8427e");
    expect(data[0].checksums.sha256).toBe(
      "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    );
  });

  it("normalizes path traversal in filenames", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/getfile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files: ["../some/file.txt"], platform: 1 }),
    });
    expect(res.status).toBe(200);
    const data: any[] = await res.json();

    // ".." is stripped, so "some/file.txt" should still match
    expect(data[0].size).toBe(50);
  });
});

// ─── /api/v1/release_info ───

describe("GET /api/v1/release_info", () => {
  it("returns decryption keys", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/release_info`);
    expect(res.status).toBe(200);
    const data = await res.json();

    expect(data).toEqual({
      "2": "w64fJz1yDElhK8ElVYxVvg==",
      "423": "UDKkj/dmBRbz+CIB+Ekqyg==",
    });
  });
});

// ─── Archive file serving ───

describe("GET /archive/...", () => {
  it("serves files from R2", async () => {
    const res = await SELF.fetch(`${BASE}/archive/iOS/update/59.2/1.zip`);
    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toBe("update-59.2-ios");
  });

  it("sets Content-Type for zip files", async () => {
    const res = await SELF.fetch(`${BASE}/archive/iOS/update/59.2/1.zip`);
    expect(res.headers.get("Content-Type")).toBe("application/zip");
  });

  it("returns 404 for non-existent archive files", async () => {
    const res = await SELF.fetch(`${BASE}/archive/iOS/nonexistent.zip`);
    expect(res.status).toBe(404);
  });
});

// ─── 404 for unknown routes ───

describe("Unknown routes", () => {
  it("returns 404 for unknown paths", async () => {
    const res = await SELF.fetch(`${BASE}/unknown`);
    expect(res.status).toBe(404);
  });

  it("returns 404 for wrong HTTP method", async () => {
    // /api/v1/update expects POST
    const res = await SELF.fetch(`${BASE}/api/v1/update`);
    expect(res.status).toBe(404);
  });
});

// ─── Response shape conformance ───

describe("Response shapes match original API", () => {
  it("DownloadInfoModel has url, size, checksums with md5/sha256", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 0, package_id: 1, platform: 1 }),
    });
    const data: any[] = await res.json();
    const item = data[0];

    // Exact shape: {url, size, checksums: {md5, sha256}}
    expect(Object.keys(item).sort()).toEqual(["checksums", "size", "url"]);
    expect(Object.keys(item.checksums).sort()).toEqual(["md5", "sha256"]);
    expect(typeof item.url).toBe("string");
    expect(typeof item.size).toBe("number");
    expect(typeof item.checksums.md5).toBe("string");
    expect(typeof item.checksums.sha256).toBe("string");
  });

  it("BatchDownloadInfoModel adds packageId field", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 0, platform: 1 }),
    });
    const data: any[] = await res.json();
    const item = data[0];

    expect(Object.keys(item).sort()).toEqual(["checksums", "packageId", "size", "url"]);
    expect(typeof item.packageId).toBe("number");
  });

  it("DownloadUpdateModel adds version field", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version: "59.0", platform: 1 }),
    });
    const data: any[] = await res.json();
    const item = data[0];

    expect(Object.keys(item).sort()).toEqual(["checksums", "size", "url", "version"]);
    expect(typeof item.version).toBe("string");
  });

  it("PublicInfoModel has correct shape", async () => {
    const res = await SELF.fetch(`${BASE}/api/publicinfo`);
    const data: any = await res.json();

    expect(Object.keys(data).sort()).toEqual([
      "application",
      "dlapiVersion",
      "gameVersion",
      "publicApi",
      "serveTimeLimit",
    ]);
    expect(Object.keys(data.dlapiVersion).sort()).toEqual(["major", "minor"]);
    expect(typeof data.publicApi).toBe("boolean");
    expect(typeof data.serveTimeLimit).toBe("number");
    expect(typeof data.gameVersion).toBe("string");
  });

  it("Error responses have detail field", async () => {
    const res = await SELF.fetch(`${BASE}/api/v1/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package_type: 0, package_id: 999, platform: 1 }),
    });
    expect(res.status).toBe(404);
    const data: any = await res.json();
    expect(Object.keys(data)).toEqual(["detail"]);
    expect(typeof data.detail).toBe("string");
  });
});
