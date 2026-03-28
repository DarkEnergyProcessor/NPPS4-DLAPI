# Script to upgrade the file "generation" from 1.1 to 1.2 to fix issue with
# data corruption during in-game download.
#
# Copyright (c) 2026 Dark Energy Processor
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import argparse
import json
import os
import pathlib

from typing import cast, TypedDict

PLATFORMS = ["iOS", "Android"]
GENERATION_VERSION: tuple[int, int] = (1, 2)
NEED_GENERATION_VERSION: tuple[int, int] = (1, 1)


class InfoV2(TypedDict):
    name: str
    size: int
    md5: str
    sha256: str


class Generation(TypedDict):
    major: int
    minor: int


def version_str(ver: tuple[int, int]):
    return "%d.%d" % ver


def read_json(file: str | pathlib.Path):
    with open(file, "r", encoding="utf-8", newline="") as f:
        return json.load(f)


def write_json(file: str | pathlib.Path, data):
    with open(file, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f)


def path_validate(path: str):
    if os.path.isdir(path):
        return os.path.normpath(path)
    raise NotADirectoryError(path)


def fixnames(path: pathlib.Path):
    infov2list: list[InfoV2] = read_json(path / "infov2.json")

    for info in infov2list:
        name, ext = os.path.splitext(info["name"])

        try:
            int(name)
        except ValueError:
            print("Skipping rename", path / info["name"])
            continue

        newname = f"{name}_{info['sha256']}{ext}"
        os.rename(path / info["name"], path / newname)
        print("Renamed", info["name"], "to", newname)
        info["name"] = newname

    infov1 = {infov2["name"]: infov2["size"] for infov2 in infov2list}
    write_json(path / "infov2.json", infov2list)
    write_json(path / "info.json", infov1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive_root", type=path_validate)
    args = parser.parse_args()

    archive_root = pathlib.Path(args.archive_root)

    genfile = archive_root / "generation.json"
    gentuple = (1, 0)
    if os.path.isfile(genfile):
        gendata: Generation = read_json(genfile)
        gentuple = (gendata["major"], gendata["minor"])

    # Check generation version
    if gentuple == GENERATION_VERSION:
        print("Up-to-date")
        return
    elif gentuple > GENERATION_VERSION:
        raise RuntimeError(
            f"Generation version is newer ({version_str(gentuple)}) than this script generation version ({version_str(GENERATION_VERSION)})"
        )
    elif gentuple < NEED_GENERATION_VERSION:
        raise RuntimeError(
            f"Generation version is older ({version_str(gentuple)}) than this script requirement generation version ({version_str(NEED_GENERATION_VERSION)})"
        )

    # Do it
    for plat in PLATFORMS:
        platdir = archive_root / plat
        if not platdir.is_dir():
            continue

        # Update files
        for ver in cast(list[str], read_json(platdir / "update" / "infov2.json")):
            fixnames(platdir / "update" / ver)

        # Package files
        for ver in cast(list[str], read_json(platdir / "package" / "info.json")):
            for package_type in range(7):
                package_path = platdir / "package" / ver / str(package_type)
                for package_id in cast(list[int], read_json(package_path / "info.json")):
                    fixnames(package_path / str(package_id))

    # Write generation file
    write_json(genfile, {"major": GENERATION_VERSION[0], "minor": GENERATION_VERSION[1]})


if __name__ == "__main__":
    main()
