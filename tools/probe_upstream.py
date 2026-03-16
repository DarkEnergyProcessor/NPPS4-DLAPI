#!/usr/bin/env python3
"""
Probe an upstream NPPS4-DLAPI server to estimate total data size
without downloading any actual files. Only calls metadata API endpoints.

Uses the same http.client approach as clone.py for compatibility.

Usage:
    python probe_upstream.py https://ll.sif.moe/npps4_dlapi
    python probe_upstream.py https://ll.sif.moe/npps4_dlapi --shared-key KEY
"""

import argparse
import http.client
import json
import urllib.parse

PACKAGE_TYPE_NAMES = {
    0: "bootstrap",
    1: "live",
    2: "scenario",
    3: "subscenario",
    4: "micro",
    5: "event_scenario",
    6: "multi_unit_scenario",
}

OS_MAP = {1: "iOS", 2: "Android"}

_http_client: http.client.HTTPSConnection | http.client.HTTPConnection | None = None


def get_client(parse: urllib.parse.ParseResult):
    """Create or reuse an HTTP(S) connection, matching clone.py's approach."""
    global _http_client
    port = parse.port or (443 if parse.scheme == "https" else 80)

    if (
        _http_client is not None
        and _http_client.host == parse.hostname
        and _http_client.port == port
    ):
        return _http_client

    if _http_client is not None:
        _http_client.close()

    cls = http.client.HTTPSConnection if parse.scheme == "https" else http.client.HTTPConnection
    _http_client = cls(parse.hostname, port, timeout=30)
    return _http_client


def api_call(base_url: str, endpoint: str, shared_key: str, body=None):
    """Call an API endpoint using the same method as clone.py."""
    parse_base = urllib.parse.urlparse(base_url)
    # Ensure trailing slash on base path (matches clone.py line 597)
    base_path = parse_base.path
    if not base_path.endswith("/"):
        base_path += "/"
    path = base_path + (endpoint[1:] if endpoint.startswith("/") else endpoint)

    client = get_client(parse_base)
    headers = {}
    if shared_key:
        headers["DLAPI-Shared-Key"] = urllib.parse.quote(shared_key)

    if body is not None:
        headers["Content-Type"] = "application/json"
        client.request("POST", path, json.dumps(body).encode("UTF-8"), headers)
    else:
        # clone.py sends json.dumps(None) = b"null" as body even for GET
        client.request("GET", path, json.dumps(None).encode("UTF-8"), headers)

    response = client.getresponse()
    data = response.read()
    if response.status != 200:
        raise RuntimeError(f"HTTP {response.status} for {path}")
    return json.loads(data)


def fmt_size(nbytes: int) -> str:
    if nbytes >= 1 << 30:
        return f"{nbytes / (1 << 30):.2f} GB"
    if nbytes >= 1 << 20:
        return f"{nbytes / (1 << 20):.2f} MB"
    if nbytes >= 1 << 10:
        return f"{nbytes / (1 << 10):.2f} KB"
    return f"{nbytes} B"


def main():
    parser = argparse.ArgumentParser(description="Probe NPPS4-DLAPI server for total data size")
    parser.add_argument("url", help="Base URL of the NPPS4-DLAPI server")
    parser.add_argument("--shared-key", default="", help="Shared key for authentication")
    parser.add_argument("--base-version", default="1.0", help="Base version for update calculation")
    args = parser.parse_args()

    base = args.url
    key = args.shared_key

    # Step 1: Public info
    print("Fetching /api/publicinfo ...")
    info = api_call(base, "api/publicinfo", key)
    print(f"  DLAPI version: {info['dlapiVersion']['major']}.{info['dlapiVersion']['minor']}")
    print(f"  Game version:  {info['gameVersion']}")
    print(f"  Public API:    {info['publicApi']}")
    print(f"  Serve time limit: {info['serveTimeLimit']}s")
    if "application" in info:
        for k, v in info["application"].items():
            print(f"  {k}: {v}")
    print()

    total_size = 0
    total_files = 0
    breakdown = {}

    # Step 2: Updates per platform
    for plat_id, plat_name in OS_MAP.items():
        print(f"Fetching /api/v1/update for {plat_name} (from {args.base_version}) ...")
        try:
            updates = api_call(base, "api/v1/update", key, {
                "version": args.base_version,
                "platform": plat_id,
            })
            size = sum(u["size"] for u in updates)
            count = len(updates)
            total_size += size
            total_files += count
            breakdown[f"{plat_name}/update"] = {"files": count, "size": size}
            print(f"  {count} files, {fmt_size(size)}")
        except Exception as e:
            print(f"  Error: {e}")
        print()

    # Step 3: Packages per platform × type
    for plat_id, plat_name in OS_MAP.items():
        for pkg_type in range(7):
            label = f"{plat_name}/package/{PACKAGE_TYPE_NAMES[pkg_type]}(type={pkg_type})"
            print(f"Fetching /api/v1/batch for {label} ...")
            try:
                batch = api_call(base, "api/v1/batch", key, {
                    "package_type": pkg_type,
                    "platform": plat_id,
                    "exclude": [],
                })
                if isinstance(batch, list):
                    size = sum(b["size"] for b in batch)
                    count = len(batch)
                    pkg_ids = set(b.get("packageId") for b in batch)
                    total_size += size
                    total_files += count
                    breakdown[label] = {"files": count, "size": size, "package_ids": len(pkg_ids)}
                    print(f"  {count} files across {len(pkg_ids)} packages, {fmt_size(size)}")
                else:
                    print(f"  (not found or empty)")
            except Exception as e:
                print(f"  Error: {e}")

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()

    for label, data in sorted(breakdown.items()):
        pkg_note = f" ({data['package_ids']} packages)" if "package_ids" in data else ""
        print(f"  {label}: {data['files']} files, {fmt_size(data['size'])}{pkg_note}")

    print()
    print(f"  Total files: {total_files}")
    print(f"  Total size:  {fmt_size(total_size)}")
    print()
    print("NOTE: This only counts files reported by update + batch APIs.")
    print("Databases (.db_), microdl assets, and metadata JSON are additional")
    print("but typically small relative to package archives.")


if __name__ == "__main__":
    main()
