#!/usr/bin/env python3
"""
Generate response snapshots from the original FastAPI implementation.

Creates a temporary archive-root directory with the same fixture data used
by the vitest Worker tests, runs every API request through FastAPI's TestClient,
and writes normalized JSON snapshots for equivalence comparison.

Usage:
    python test/generate_snapshots.py
"""

import base64
import json
import os
import re
import sys
import tempfile

# ── Fixture data (mirrors test/fixtures.ts exactly) ──

FIXTURES: dict[str, str | object] = {
    # Generation marker
    "generation.json": {"major": 1, "minor": 1},

    # Release info
    "release_info.json": {
        "2": "w64fJz1yDElhK8ElVYxVvg==",
        "423": "UDKkj/dmBRbz+CIB+Ekqyg==",
    },

    # iOS update
    "iOS/update/infov2.json": ["59.2", "59.4"],
    "iOS/update/59.2/infov2.json": [
        {
            "name": "1.zip",
            "size": 15,
            "md5": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
            "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb01",
        },
    ],
    "iOS/update/59.2/1.zip": "update-59.2-ios",
    "iOS/update/59.4/infov2.json": [
        {
            "name": "1.zip",
            "size": 15,
            "md5": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2",
            "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb02",
        },
    ],
    "iOS/update/59.4/1.zip": "update-59.4-ios",

    # iOS packages
    "iOS/package/info.json": ["59.4"],

    # Bootstrap packages (type 0), IDs 1 and 2
    "iOS/package/59.4/0/info.json": [1, 2],
    "iOS/package/59.4/0/1/infov2.json": [
        {
            "name": "1.zip",
            "size": 300,
            "md5": "cccccccccccccccccccccccccccccccc",
            "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd01",
        },
    ],
    "iOS/package/59.4/0/1/1.zip": "pkg-0-1-ios",
    "iOS/package/59.4/0/2/infov2.json": [
        {
            "name": "1.zip",
            "size": 400,
            "md5": "cccccccccccccccccccccccccccccc02",
            "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd02",
        },
        {
            "name": "2.zip",
            "size": 350,
            "md5": "cccccccccccccccccccccccccccccc03",
            "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd03",
        },
    ],
    "iOS/package/59.4/0/2/1.zip": "pkg-0-2-1-ios",
    "iOS/package/59.4/0/2/2.zip": "pkg-0-2-2-ios",

    # Micro packages (type 4), ID 100
    "iOS/package/59.4/4/info.json": [100],
    "iOS/package/59.4/4/100/infov2.json": [
        {
            "name": "1.zip",
            "size": 500,
            "md5": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        },
    ],
    "iOS/package/59.4/4/100/1.zip": "pkg-4-100-ios",

    # Database
    "iOS/package/59.4/db/testdb.db_": "FAKE-SQLITE3-DATA",

    # Micro download map
    "iOS/package/59.4/microdl/info.json": {
        "some/file.txt": {
            "size": 50,
            "md5": "11111111111111111111111111111111",
            "sha256": "2222222222222222222222222222222222222222222222222222222222222222",
        },
        "another/asset.png": {
            "size": 1024,
            "md5": "33333333333333333333333333333333",
            "sha256": "4444444444444444444444444444444444444444444444444444444444444444",
        },
    },
    "iOS/package/59.4/microdl/some/file.txt": "micro-file-content",
    "iOS/package/59.4/microdl/another/asset.png": "micro-asset-content",

    # Android update
    "Android/update/infov2.json": ["59.4"],
    "Android/update/59.4/infov2.json": [
        {
            "name": "1.zip",
            "size": 250,
            "md5": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa3",
            "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb03",
        },
    ],
    "Android/update/59.4/1.zip": "update-59.4-android",

    # Android packages
    "Android/package/info.json": ["59.4"],
    "Android/package/59.4/0/info.json": [1],
    "Android/package/59.4/0/1/infov2.json": [
        {
            "name": "1.zip",
            "size": 320,
            "md5": "cccccccccccccccccccccccccccccc04",
            "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd04",
        },
    ],
    "Android/package/59.4/0/1/1.zip": "pkg-0-1-android",
    "Android/package/59.4/db/androidtest.db_": "FAKE-ANDROID-SQLITE3",
    "Android/package/59.4/microdl/info.json": {},
}


def materialize_fixtures(root: str):
    """Write all fixture data to a directory tree."""
    for path, content in FIXTURES.items():
        fullpath = os.path.join(root, path)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        if isinstance(content, str):
            with open(fullpath, "w", encoding="UTF-8") as f:
                f.write(content)
        else:
            with open(fullpath, "w", encoding="UTF-8") as f:
                json.dump(content, f)


def normalize_url(url: str) -> str:
    """
    Strip the origin and static-mount prefix from URLs so that both
    implementations can be compared. FastAPI produces URLs like
    'http://testserver/archive-root/iOS/...' and the Worker produces
    'http://localhost/archive/iOS/...'. We normalize both to just
    'iOS/...' (the relative archive path).
    """
    # Remove everything up to and including /archive-root/ or /archive/
    url = re.sub(r"^https?://[^/]+/archive(?:-root)?/", "", url)
    return url


def normalize_body(body):
    """Recursively normalize URLs in response bodies."""
    if isinstance(body, dict):
        result = {}
        for k, v in body.items():
            if k == "url" and isinstance(v, str):
                result[k] = normalize_url(v)
            else:
                result[k] = normalize_body(v)
        return result
    elif isinstance(body, list):
        return [normalize_body(item) for item in body]
    return body


# ── Request catalog ──
# Each entry: (key, method, path, body_or_None)

REQUEST_CATALOG = [
    # publicinfo
    ("publicinfo", "GET", "/api/publicinfo", None),

    # update
    ("update-ios-from-59.0", "POST", "/api/v1/update",
     {"version": "59.0", "platform": 1}),
    ("update-ios-from-59.2", "POST", "/api/v1/update",
     {"version": "59.2", "platform": 1}),
    ("update-ios-at-latest", "POST", "/api/v1/update",
     {"version": "59.4", "platform": 1}),
    ("update-android-from-59.0", "POST", "/api/v1/update",
     {"version": "59.0", "platform": 2}),

    # batch
    ("batch-ios-type0", "POST", "/api/v1/batch",
     {"package_type": 0, "platform": 1, "exclude": []}),
    ("batch-ios-type0-exclude2", "POST", "/api/v1/batch",
     {"package_type": 0, "platform": 1, "exclude": [2]}),
    ("batch-ios-type3-notfound", "POST", "/api/v1/batch",
     {"package_type": 3, "platform": 1, "exclude": []}),
    ("batch-ios-no-exclude-field", "POST", "/api/v1/batch",
     {"package_type": 0, "platform": 1}),

    # download
    ("download-ios-0-2", "POST", "/api/v1/download",
     {"package_type": 0, "package_id": 2, "platform": 1}),
    ("download-ios-0-999-notfound", "POST", "/api/v1/download",
     {"package_type": 0, "package_id": 999, "platform": 1}),
    ("download-android-0-1", "POST", "/api/v1/download",
     {"package_type": 0, "package_id": 1, "platform": 2}),

    # getdb
    ("getdb-testdb", "GET", "/api/v1/getdb/testdb", None),
    ("getdb-notfound", "GET", "/api/v1/getdb/nonexistent", None),
    ("getdb-sanitize", "GET", "/api/v1/getdb/test..db", None),

    # getfile
    ("getfile-single", "POST", "/api/v1/getfile",
     {"files": ["some/file.txt"], "platform": 1}),
    ("getfile-multi", "POST", "/api/v1/getfile",
     {"files": ["some/file.txt", "another/asset.png"], "platform": 1}),
    ("getfile-unknown", "POST", "/api/v1/getfile",
     {"files": ["nonexistent/file.bin"], "platform": 1}),
    ("getfile-traversal", "POST", "/api/v1/getfile",
     {"files": ["../some/file.txt"], "platform": 1}),

    # release_info
    ("release-info", "GET", "/api/v1/release_info", None),
]


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_root = os.path.join(tmpdir, "archive-root")
        os.makedirs(archive_root)
        materialize_fixtures(archive_root)

        # Write a minimal config.toml
        config_path = os.path.join(tmpdir, "config.toml")
        with open(config_path, "w") as f:
            f.write(f'[main]\npublic = true\nshared_key = ""\n')
            f.write(f'archive_root = "{archive_root}"\n')

        # Set environment and import FastAPI app
        os.environ["N4DLAPI_CONFIG_FILE"] = config_path
        sys.path.insert(0, os.path.join(project_root, "fastapi"))

        # Need to import AFTER setting env vars, since config.init() runs at import time
        from n4dlapi.main import app
        from starlette.testclient import TestClient

        client = TestClient(app)

        snapshots: dict[str, dict] = {}

        for key, method, path, body in REQUEST_CATALOG:
            if method == "GET":
                resp = client.get(path)
            else:
                resp = client.post(path, json=body)

            snapshot: dict = {"status": resp.status_code}

            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                json_body = resp.json()
                # For publicinfo, remove implementation-specific fields
                if key == "publicinfo" and isinstance(json_body, dict):
                    app_info = json_body.get("application", {})
                    # Keep only NPPS4DLAPIVersion
                    json_body["application"] = {
                        "NPPS4DLAPIVersion": app_info.get(
                            "NPPS4DLAPIVersion",
                            app_info.get("NPPS4DLAPIVersion", ""),
                        ),
                    }
                snapshot["body"] = normalize_body(json_body)
            elif "sqlite3" in content_type or "octet-stream" in content_type:
                # Binary response - encode as base64
                snapshot["body_base64"] = base64.b64encode(resp.content).decode("ascii")
                snapshot["content_type"] = content_type
                if "content-disposition" in resp.headers:
                    snapshot["content_disposition"] = resp.headers["content-disposition"]
            else:
                # Text or other
                snapshot["body"] = resp.text

            snapshots[key] = snapshot

        # Write snapshots
        output_path = os.path.join(project_root, "test", "snapshots", "fastapi-responses.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="UTF-8") as f:
            json.dump(snapshots, f, indent=2, ensure_ascii=False)

        print(f"Generated {len(snapshots)} snapshots -> {output_path}")


if __name__ == "__main__":
    main()
