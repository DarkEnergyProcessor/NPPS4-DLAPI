/**
 * Test fixtures that populate an R2 bucket with a minimal archive-root structure
 * mirroring the directory layout the original FastAPI implementation expects.
 *
 * Structure:
 *   iOS/
 *     update/
 *       infov2.json            -> ["59.2", "59.4"]
 *       59.2/infov2.json       -> [{name:"1.zip", size:100, md5:..., sha256:...}]
 *       59.2/1.zip             -> (binary)
 *       59.4/infov2.json       -> [{name:"1.zip", size:200, md5:..., sha256:...}]
 *       59.4/1.zip             -> (binary)
 *     package/
 *       info.json              -> ["59.4"]
 *       59.4/
 *         0/info.json          -> [1, 2]
 *         0/1/infov2.json      -> [{name:"1.zip", ...}]
 *         0/1/1.zip            -> (binary)
 *         0/2/infov2.json      -> [{name:"1.zip", ...}]
 *         0/2/1.zip            -> (binary)
 *         4/info.json          -> [100]
 *         4/100/infov2.json    -> [{name:"1.zip", ...}]
 *         4/100/1.zip          -> (binary)
 *         db/testdb.db_        -> (binary)
 *         microdl/info.json    -> {"some/file.txt": {size:50, md5:..., sha256:...}}
 *         microdl/some/file.txt -> (binary)
 *   Android/
 *     update/
 *       infov2.json            -> ["59.4"]
 *       59.4/infov2.json       -> [{name:"1.zip", ...}]
 *       59.4/1.zip             -> (binary)
 *     package/
 *       info.json              -> ["59.4"]
 *       59.4/
 *         0/info.json          -> [1]
 *         0/1/infov2.json      -> [{name:"1.zip", ...}]
 *         0/1/1.zip            -> (binary)
 *         db/androidtest.db_   -> (binary)
 *         microdl/info.json    -> {}
 *   release_info.json          -> {"2":"w64fJz1yDElhK8ElVYxVvg==","423":"UDKkj/dmBRbz+CIB+Ekqyg=="}
 */

// Pre-computed hashes for deterministic test data
// Content "update-59.2-ios" -> md5/sha256
const FIXTURES: Record<string, string | object> = {
  // ── Release info ──
  "release_info.json": {
    "2": "w64fJz1yDElhK8ElVYxVvg==",
    "423": "UDKkj/dmBRbz+CIB+Ekqyg==",
  },

  // ── iOS update ──
  "iOS/update/infov2.json": ["59.2", "59.4"],
  "iOS/update/59.2/infov2.json": [
    {
      name: "1.zip",
      size: 15,
      md5: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
      sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb01",
    },
  ],
  "iOS/update/59.2/1.zip": "update-59.2-ios",
  "iOS/update/59.4/infov2.json": [
    {
      name: "1.zip",
      size: 15,
      md5: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2",
      sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb02",
    },
  ],
  "iOS/update/59.4/1.zip": "update-59.4-ios",

  // ── iOS packages ──
  "iOS/package/info.json": ["59.4"],

  // Bootstrap packages (type 0), IDs 1 and 2
  "iOS/package/59.4/0/info.json": [1, 2],
  "iOS/package/59.4/0/1/infov2.json": [
    {
      name: "1.zip",
      size: 300,
      md5: "cccccccccccccccccccccccccccccccc",
      sha256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd01",
    },
  ],
  "iOS/package/59.4/0/1/1.zip": "pkg-0-1-ios",
  "iOS/package/59.4/0/2/infov2.json": [
    {
      name: "1.zip",
      size: 400,
      md5: "cccccccccccccccccccccccccccccc02",
      sha256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd02",
    },
    {
      name: "2.zip",
      size: 350,
      md5: "cccccccccccccccccccccccccccccc03",
      sha256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd03",
    },
  ],
  "iOS/package/59.4/0/2/1.zip": "pkg-0-2-1-ios",
  "iOS/package/59.4/0/2/2.zip": "pkg-0-2-2-ios",

  // Micro packages (type 4), ID 100
  "iOS/package/59.4/4/info.json": [100],
  "iOS/package/59.4/4/100/infov2.json": [
    {
      name: "1.zip",
      size: 500,
      md5: "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
      sha256: "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    },
  ],
  "iOS/package/59.4/4/100/1.zip": "pkg-4-100-ios",

  // Database
  "iOS/package/59.4/db/testdb.db_": "FAKE-SQLITE3-DATA",

  // Micro download map
  "iOS/package/59.4/microdl/info.json": {
    "some/file.txt": {
      size: 50,
      md5: "11111111111111111111111111111111",
      sha256: "2222222222222222222222222222222222222222222222222222222222222222",
    },
    "another/asset.png": {
      size: 1024,
      md5: "33333333333333333333333333333333",
      sha256: "4444444444444444444444444444444444444444444444444444444444444444",
    },
  },
  "iOS/package/59.4/microdl/some/file.txt": "micro-file-content",
  "iOS/package/59.4/microdl/another/asset.png": "micro-asset-content",

  // ── Android update ──
  "Android/update/infov2.json": ["59.4"],
  "Android/update/59.4/infov2.json": [
    {
      name: "1.zip",
      size: 250,
      md5: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa3",
      sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb03",
    },
  ],
  "Android/update/59.4/1.zip": "update-59.4-android",

  // ── Android packages ──
  "Android/package/info.json": ["59.4"],
  "Android/package/59.4/0/info.json": [1],
  "Android/package/59.4/0/1/infov2.json": [
    {
      name: "1.zip",
      size: 320,
      md5: "cccccccccccccccccccccccccccccc04",
      sha256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd04",
    },
  ],
  "Android/package/59.4/0/1/1.zip": "pkg-0-1-android",
  "Android/package/59.4/db/androidtest.db_": "FAKE-ANDROID-SQLITE3",
  "Android/package/59.4/microdl/info.json": {},
};

export async function seedBucket(bucket: R2Bucket): Promise<void> {
  const puts = Object.entries(FIXTURES).map(([key, value]) => {
    const body = typeof value === "string" ? value : JSON.stringify(value);
    return bucket.put(key, body);
  });
  await Promise.all(puts);
}
