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

import json
import os

import natsort

from . import config
from . import model

from typing import Any, Callable, TypeVar, Generic

_T = TypeVar("_T")

_PLATFORM_MAP = ["iOS", "Android"]


class MemoizeByModTime(Generic[_T]):
    def __init__(self, f: Callable[[str], _T]):
        self.f = f
        self.map: dict[str, tuple[int, _T]] = {}

    def __call__(self, path: str):
        stat = os.stat(path)
        if path in self.map:
            mtime, result = self.map[path]
            if stat.st_mtime_ns <= mtime:
                return result
        result = self.f(path)
        self.map[path] = (stat.st_mtime_ns, result)
        return result


@MemoizeByModTime
def read_json(file: str):
    with open(file, "r", encoding="UTF-8", newline="") as f:
        return json.load(f)


def parse_sifversion(ver: str):
    major, minor = ver.split(".", 2)
    return int(major), int(minor)


def version_string(ver: tuple[int, int]):
    return "%d.%d" % ver


@MemoizeByModTime
def get_versions(file: str):
    versions: list[str] = read_json(file)
    new_ver: list[tuple[int, int]] = []
    for ver in versions:
        try:
            new_ver.append(parse_sifversion(ver))
        except ValueError:
            pass
    new_ver.sort()
    return new_ver


def get_latest_version():
    update_ios: list[str] = natsort.natsorted(read_json(config.get_archive_root_dir() + "/iOS/package/info.json"))
    update_android: list[str] = natsort.natsorted(
        read_json(config.get_archive_root_dir() + "/Android/package/info.json")
    )
    if update_ios[-1] != update_android[-1]:
        raise RuntimeError(f"Latest version discrepancy detected (iOS {update_ios}, Android {update_android})")
    return parse_sifversion(update_ios[-1])


def get_release_info():
    release_info: dict[str, str] = read_json(config.get_archive_root_dir() + "/release_info.json")
    return release_info


def get_update_file(old_client_version: str, platform: int):
    path = f"{config.get_archive_root_dir()}/{_PLATFORM_MAP[platform - 1]}/update"
    archive_root_len = len(config.get_archive_root_dir())
    current_version = parse_sifversion(old_client_version)
    updates = get_versions(path + "/infov2.json")
    if current_version == updates[-1]:
        # Up-to-date
        return []

    # Get download files
    download_data: list[model.DownloadInfoModel] = []
    for ver in filter(lambda x: x > current_version, updates):
        update_ver_path = f"{path}/{version_string(ver)}"
        file_datas: list[dict[str, Any]] = read_json(update_ver_path + "/infov2.json")
        for filedata in file_datas:
            fullpath = f"{update_ver_path}/{filedata['name']}"
            download_data.append(
                model.DownloadInfoModel(
                    url=fullpath[archive_root_len:],
                    size=filedata["size"],
                    checksums=model.ChecksumModel(md5=filedata["md5"], sha256=filedata["sha256"]),
                )
            )
    return download_data


def get_batch_list(pkgtype: int, platform: int, exclude: list[int]):
    latest = get_latest_version()
    path = f"{config.get_archive_root_dir()}/{_PLATFORM_MAP[platform - 1]}/package/{version_string(latest)}/{pkgtype}"
    if not os.path.isdir(path):
        # Not found
        return None

    archive_root_len = len(config.get_archive_root_dir())
    result: list[model.BatchDownloadInfoModel] = []
    packages: list[int] = read_json(path + "/info.json")

    for pkgid in sorted(set(packages).difference(exclude)):
        file_datas: list[dict[str, Any]] = read_json(f"{path}/{pkgid}/infov2.json")
        for filedata in file_datas:
            fullpath = f"{path}/{pkgid}/{filedata['name']}"
            result.append(
                model.BatchDownloadInfoModel(
                    url=fullpath[archive_root_len:],
                    size=filedata["size"],
                    checksums=model.ChecksumModel(md5=filedata["md5"], sha256=filedata["sha256"]),
                    packageId=pkgid,
                )
            )

    return result


def get_single_package(pkgtype: int, pkgid: int, platform: int):
    latest = get_latest_version()
    path = f"{config.get_archive_root_dir()}/{_PLATFORM_MAP[platform - 1]}/package/{version_string(latest)}/{pkgtype}/{pkgid}"
    if not os.path.isdir(path):
        return None

    archive_root_len = len(config.get_archive_root_dir())

    result: list[model.DownloadInfoModel] = []
    file_datas: list[dict[str, Any]] = read_json(f"{path}/infov2.json")
    for filedata in file_datas:
        fullpath = f"{path}/{filedata['name']}"
        result.append(
            model.DownloadInfoModel(
                url=fullpath[archive_root_len:],
                size=filedata["size"],
                checksums=model.ChecksumModel(md5=filedata["md5"], sha256=filedata["sha256"]),
            )
        )

    return result


def get_database_file(name: str):
    latest = get_latest_version()
    dbname = "".join(filter(lambda x: x.isalnum() or x == "_", name))
    path = f"{config.get_archive_root_dir()}/Android/package/{version_string(latest)}/db/{dbname}.db_"
    try:
        with open(path, "rb") as f:
            return f.read()
    except IOError:
        return None


def get_microdl_file(file: str, platform: int):
    latest = get_latest_version()
    # Normalize path
    commonpath = f"{_PLATFORM_MAP[platform - 1]}/package/{version_string(latest)}/microdl"
    basepath = f"{config.get_archive_root_dir()}/{commonpath}"
    microdl_map: dict[str, dict[str, Any]] = read_json(basepath + "/info.json")
    sanitized_file = os.path.normpath(file.replace("..", "")).replace("\\", "/")
    if sanitized_file[0] == "/":
        sanitized_file = sanitized_file[1:]
    path = f"{commonpath}/{sanitized_file}"

    # Get microdl_map
    result = model.DownloadInfoModel(
        url=path,
        size=0,
        checksums=model.ChecksumModel(
            md5="d41d8cd98f00b204e9800998ecf8427e",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ),
    )
    if sanitized_file in microdl_map:
        info = microdl_map[sanitized_file]
        result.size = info["size"]
        result.checksums.md5 = info["md5"]
        result.checksums.sha256 = info["sha256"]

    return result
