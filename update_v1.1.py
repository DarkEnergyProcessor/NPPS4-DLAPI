# Copyright (c) 2023 Dark Energy Processor
#
# This software is provided 'as-is', without any express or implied
# warranty. In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.

import argparse
import functools
import hashlib
import io
import json
import os
import zipfile

import natsort
import honkypy

from typing import Any, Literal

PLATFORMS = ["iOS", "Android"]
GENERATION_VERSION = (1, 1)


@functools.cache
def read_json(file: str):
    with open(file, "r", encoding="UTF-8", newline="") as f:
        return json.load(f)


def write_json(file: str, data: list | dict):
    with open(file, "w", encoding="UTF-8", newline="") as f:
        json.dump(data, f)


@functools.cache
def parse_version(ver: str):
    versions = ver.split(".", 1)
    return int(versions[0]), int(versions[1])


@functools.cache
def version_str(ver: tuple[int, int]):
    return "%d.%d" % ver


def get_versions(file: str):
    versions: list[str] = read_json(file)
    new_ver: list[tuple[int, int]] = []
    for ver in versions:
        try:
            new_ver.append(parse_version(ver))
        except ValueError:
            pass
    new_ver.sort()
    return new_ver


def build_new_update_info(root: str, platform: str):
    path = f"{root}/{platform}/update"
    versions: list[tuple[int, int]] = []
    # Scan update files in update.
    for file in os.scandir(path):
        if file.is_dir():
            try:
                versions.append(parse_version(file.name))
            except ValueError:
                pass
    versions.sort()
    write_json(f"{path}/infov2.json", list(map(version_str, versions)))


def prehash_update(root: str, platform: str):
    path = f"{root}/{platform}/update"

    # Hash them
    for version in get_versions(path + "/infov2.json"):
        verstr = version_str(version)
        print("Making new metadata for update ", verstr)
        infov2: list[dict[str, Any]] = []
        verpath = f"{path}/{verstr}/"
        verinfo: dict[str, int] = read_json(verpath + "info.json")
        verdata: list[tuple[str, int]] = natsort.natsorted(verinfo.items(), key=lambda x: x[0])
        for data in verdata:
            archive = verpath + data[0]
            with open(archive, "rb") as f:
                archive_data = f.read()
            md5: str = hashlib.md5(archive_data, usedforsecurity=False).digest().hex()
            sha256: str = hashlib.sha256(archive_data, usedforsecurity=False).digest().hex()
            infov2.append({"name": data[0], "size": data[1], "md5": md5, "sha256": sha256})
        write_json(verpath + "infov2.json", infov2)


def get_db_from_update(root: str, platform: str, uptover: tuple[int, int]):
    path = f"{root}/{platform}/update"
    dbfiles: dict[str, bytes] = {}

    # Load them
    for version in filter(lambda x: x <= uptover, get_versions(path + "/infov2.json")):
        verstr = version_str(version)
        print("Making new metadata for update ", verstr)
        verpath = f"{path}/{verstr}/"
        verinfo: list[dict[str, Any]] = read_json(verpath + "infov2.json")
        for archive in verinfo:
            archive_path = verpath + archive["name"]
            with open(archive_path, "rb") as f:
                archive_data = f.read()
            with zipfile.ZipFile(io.BytesIO(archive_data), "r") as z:
                for info in z.infolist():
                    if info.filename.startswith("db/") and info.filename.endswith(".db_"):
                        with z.open(info, "r") as f:
                            dbname = os.path.basename(info.filename)
                            print("Adding db file", dbname)
                            dbfiles[dbname] = f.read()

    return dbfiles


def prehash_package_type(
    root: str,
    platform: str,
    version: tuple[int, int],
    pkgtype: int,
    *,
    dbfiles: dict[str, bytes] | None = None,
    extract_to: str | None = None,
):
    path = f"{root}/{platform}/package/{version_str(version)}/{pkgtype}"
    pkg_ids: list[int] = read_json(f"{path}/info.json")
    # Create new hash
    for id in pkg_ids:
        print("Making new metadata for package", pkgtype, id)
        path_id = f"{path}/{id}"
        infov2: list[dict[str, Any]] = []
        verinfo: dict[str, int] = read_json(f"{path_id}/info.json")
        verdata: list[tuple[str, int]] = natsort.natsorted(verinfo.items(), key=lambda x: x[0])
        for data in verdata:
            archive = f"{path_id}/{data[0]}"
            with open(archive, "rb") as f:
                archive_data = f.read()
            if dbfiles is not None:
                with zipfile.ZipFile(io.BytesIO(archive_data), "r") as z:
                    for info in z.infolist():
                        if info.filename.startswith("db/") and info.filename.endswith(".db_"):
                            with z.open(info, "r") as f:
                                dbname = os.path.basename(info.filename)
                                print("Adding db file", dbname)
                                dbfiles[dbname] = f.read()
            md5: str = hashlib.md5(archive_data, usedforsecurity=False).digest().hex()
            sha256: str = hashlib.sha256(archive_data, usedforsecurity=False).digest().hex()
            infov2.append({"name": data[0], "size": data[1], "md5": md5, "sha256": sha256})
        # Write new hash
        write_json(f"{path_id}/infov2.json", infov2)

    # Extract microdl
    if extract_to is not None:
        extract_data: dict[str, dict[str, Any]] = {}
        for id in reversed(pkg_ids):
            path_id = f"{path}/{id}/"
            verinfo2: list[dict[str, Any]] = read_json(f"{path_id}/infov2.json")
            print("Extracting", pkgtype, id, "for microdl")
            name: str
            for name in map(lambda x: x["name"], reversed(verinfo2)):
                # Open archive for microdl extract
                with zipfile.ZipFile(f"{path_id}/{name}", "r") as z:
                    for info in z.infolist():
                        if info.filename not in extract_data:
                            print("Extracting", info.filename)
                            with z.open(info, "r") as f:
                                filedata = f.read()
                            # Hash
                            md5: str = hashlib.md5(filedata, usedforsecurity=False).digest().hex()
                            sha256: str = hashlib.sha256(filedata, usedforsecurity=False).digest().hex()
                            extract_data[info.filename] = {"size": len(filedata), "md5": md5, "sha256": sha256}
                            # Write file
                            filepath = f"{extract_to}/{info.filename}"
                            os.makedirs(os.path.dirname(filepath), exist_ok=True)
                            with open(filepath, "wb") as f:
                                f.write(filedata)
        print("Writing microdl hashes")
        write_json(f"{extract_to}/info.json", extract_data)


def prehash_packages(root: str, platform: str):
    path = f"{root}/{platform}/package"
    info = get_versions(f"{path}/info.json")
    for version in info:
        dbfiles = get_db_from_update(root, platform, version)
        # Prehash
        print("Prehasing package for version", *version)
        verstr = version_str(version)
        microdl_dest = f"{path}/{verstr}/microdl"
        for pkgtype in range(7):
            prehash_package_type(
                root,
                platform,
                version,
                pkgtype,
                dbfiles=dbfiles if pkgtype == 0 else None,
                extract_to=microdl_dest if pkgtype == 4 else None,
            )
        # Write decrypted db
        dbpath = f"{path}/{verstr}/db"
        os.makedirs(dbpath, exist_ok=True)
        for name, db in dbfiles.items():
            print("Writing decrypted db", name)
            dctx, _ = honkypy.decrypt_setup_probe(name, db[:16])
            with open(f"{dbpath}/{name}", "wb") as f:
                f.write(dctx.decrypt_block(db[dctx.HEADER_SIZE :]))


def path_validate(path: str):
    if os.path.isdir(path):
        return os.path.normpath(path)
    raise NotADirectoryError(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive_root", type=path_validate)
    args = parser.parse_args()

    root: str = args.archive_root
    # Load generation version
    genfile = f"{root}/generation.json"
    if os.path.isfile(genfile):
        gendata: dict[Literal["major", "minor"], int] = read_json(genfile)
        gentuple = (gendata["major"], gendata["minor"])
    else:
        gentuple = (1, 0)

    # Check generation version
    if gentuple == GENERATION_VERSION:
        print("Up-to-date")
        return
    elif gentuple > GENERATION_VERSION:
        raise RuntimeError(
            f"Generation version is newer ({version_str(gentuple)}) than this script generation version ({version_str(GENERATION_VERSION)})"
        )

    # Update
    for platform in PLATFORMS:
        print("===== OS:", platform, "=====")
        print("Writing new update metadata")
        build_new_update_info(root, platform)
        prehash_update(root, platform)
        prehash_packages(root, platform)

    # Write generation file
    write_json(genfile, {"major": GENERATION_VERSION[0], "minor": GENERATION_VERSION[1]})


if __name__ == "__main__":
    main()
