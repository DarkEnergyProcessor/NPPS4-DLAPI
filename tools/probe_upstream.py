#!/usr/bin/env python3
"""
Probe an upstream NPPS4-DLAPI server to estimate total data size
without downloading any actual files. Only calls metadata API endpoints.

Usage:
    python probe_upstream.py https://ll.sif.moe/npps4_dlapi
    python probe_upstream.py https://ll.sif.moe/npps4_dlapi --shared-key KEY
"""

import argparse
import json
import sys
import urllib.request

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


def api_call(base_url: str, endpoint: str, shared_key: str, body=None):
    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
    else:
        req = urllib.request.Request(url, method="GET")
    if shared_key:
        req.add_header("DLAPI-Shared-Key", shared_key)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


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
                    # Count unique package IDs
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

    for label, info in sorted(breakdown.items()):
        pkg_note = f" ({info['package_ids']} packages)" if "package_ids" in info else ""
        print(f"  {label}: {info['files']} files, {fmt_size(info['size'])}{pkg_note}")

    print()
    print(f"  Total files: {total_files}")
    print(f"  Total size:  {fmt_size(total_size)}")
    print()
    print("NOTE: This only counts files reported by update + batch APIs.")
    print("Databases (.db_), microdl assets, and metadata JSON are additional")
    print("but typically small relative to package archives.")


if __name__ == "__main__":
    main()
