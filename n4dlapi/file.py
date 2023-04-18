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

import hashlib
import json
import os
import random
import threading
import zipfile

import natsort

from . import config
from . import crypt
from . import model

from typing import Callable, TypeVar, Generic

_T = TypeVar("_T")

_PLATFORM_MAPPING = ["iOS", "Android"]
_DB_LOCK = threading.Lock()
_MICRODL_LOCK = threading.Lock()


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
def hash_file(file: str) -> tuple[str, str]:
    with open(file, "rb") as f:
        contents = f.read()
    return (
        hashlib.md5(contents, usedforsecurity=False).hexdigest(),
        hashlib.sha256(contents, usedforsecurity=False).hexdigest(),
    )


@MemoizeByModTime
def read_json(file: str):
    with open(file, "r", encoding="UTF-8", newline="") as f:
        return json.load(f)


def parse_sifversion(ver: str):
    major, minor = ver.split(".", 2)
    return int(major), int(minor)


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
    path = config.get_archive_root_dir() + "/" + _PLATFORM_MAPPING[platform - 1] + "/update"
    archive_root_len = len(config.get_archive_root_dir())
    current_version = parse_sifversion(old_client_version)
    latest_update = parse_sifversion(natsort.natsorted(read_json(path + "/info.json"))[-1])
    if current_version == latest_update:
        # Up-to-date
        return []

    # Get version list
    update_list: list[tuple[int, int]] = []
    for entry in os.scandir(path):
        if entry.is_dir():
            try:
                ver = parse_sifversion(entry.name)
                if ver > current_version:
                    update_list.append(ver)
            except ValueError:
                pass
    update_list.sort()

    # Get download files
    download_data: list[model.DownloadInfoModel] = []
    for ver in update_list:
        files: list[tuple[str, int]] = natsort.natsorted(
            read_json(path + ("/%s.%s" % ver) + "/info.json").items(), key=lambda x: x[0]
        )
        for file, size in files:
            fullpath = path + ("/%s.%s/" % ver) + file
            md5, sha256 = hash_file(fullpath)
            download_data.append(
                model.DownloadInfoModel(
                    url=fullpath[archive_root_len:],
                    size=size,
                    checksums=model.ChecksumModel(md5=md5, sha256=sha256),
                )
            )
    return download_data


def get_batch_list(package_type: int, platform: int, exclude: list[int]):
    latest = get_latest_version()
    path = (
        config.get_archive_root_dir()
        + "/"
        + _PLATFORM_MAPPING[platform - 1]
        + "/package/"
        + ("%s.%s/" % latest)
        + str(package_type)
    )
    if not os.path.isdir(path):
        # Not found
        return None

    archive_root_len = len(config.get_archive_root_dir())

    result: list[model.BatchDownloadInfoModel] = []
    packages: list[int] = read_json(path + "/info.json")

    for package_id in sorted(set(packages).difference(exclude)):
        files: list[tuple[str, int]] = natsort.natsorted(
            read_json(f"{path}/{package_id}/info.json").items(), key=lambda x: x[0]
        )
        for file, size in files:
            fullpath = f"{path}/{package_id}/{file}"
            md5, sha256 = hash_file(fullpath)
            result.append(
                model.BatchDownloadInfoModel(
                    url=fullpath[archive_root_len:],
                    size=size,
                    checksums=model.ChecksumModel(md5=md5, sha256=sha256),
                    packageId=package_id,
                )
            )

    return result


def get_single_package(package_type: int, package_id: int, platform: int):
    latest = get_latest_version()
    path = (
        config.get_archive_root_dir()
        + "/"
        + _PLATFORM_MAPPING[platform - 1]
        + "/package/"
        + ("%s.%s/" % latest)
        + f"{package_type}/{package_id}"
    )
    if not os.path.isdir(path):
        return None

    archive_root_len = len(config.get_archive_root_dir())

    result: list[model.DownloadInfoModel] = []
    files: list[tuple[str, int]] = natsort.natsorted(read_json(path + "/info.json").items(), key=lambda x: x[0])
    for file, size in files:
        fullpath = f"{path}/{file}"
        md5, sha256 = hash_file(fullpath)
        result.append(
            model.DownloadInfoModel(
                url=fullpath[archive_root_len:],
                size=size,
                checksums=model.ChecksumModel(md5=md5, sha256=sha256),
            )
        )

    return result


@MemoizeByModTime
def get_dbs_in_archive(file: str):
    result: list[tuple[str, str]] = []
    with zipfile.ZipFile(file, "r") as z:
        for info in z.infolist():
            if info.filename.startswith("db/") and info.filename.endswith(".db_"):
                filename, _ = os.path.splitext(os.path.basename(info.filename))
                result.append((filename, info.filename))
    return result


@MemoizeByModTime
def get_file_info(file: str):
    stat = os.stat(file)
    return stat.st_size, *hash_file(file)


def get_database_file(name: str):
    static_dir = config.get_static_dir()
    latest = get_latest_version()
    db_dir = f"{static_dir}/db/{latest[0]}.{latest[1]}"

    cached_db = f"{db_dir}/{name}.db_"
    if os.path.isfile(cached_db):
        with open(cached_db, "rb") as f:
            return f.read()

    with _DB_LOCK:
        os.makedirs(db_dir, exist_ok=True)
        db = _get_database_file_from_archive(name)
        if db:
            with open(cached_db, "wb") as f:
                f.write(db)
    return db


def _get_database_file_from_archive(name: str):
    # Find in package 0 first. Platform doesn't matter.
    package_0 = get_single_package(0, 0, random.randint(1, 2))
    if package_0 is None:
        raise RuntimeError("Missing package type 0")

    db = _get_database_file_from_archive_impl(name, package_0)
    if db is None:
        # Find in update files.
        lowest = (get_latest_version()[0], 0)
        updates = get_update_file("%s.%s" % lowest, random.randint(1, 2))

        db = _get_database_file_from_archive_impl(name, updates)

    return db


def _get_database_file_from_archive_impl(name: str, download_files: list[model.DownloadInfoModel]):
    archive_root = config.get_archive_root_dir()
    for download in reversed(download_files):
        filename = archive_root + download.url
        dbs = get_dbs_in_archive(filename)
        for dbname, dbpath in dbs:
            if dbname == name:
                # This is what we're looking for
                with zipfile.ZipFile(filename, "r") as z:
                    with z.open(dbpath, "r") as f:
                        return crypt.decrypt(dbpath, f.read())
    return None


def get_microdl_file(file: str, platform: int):
    # Normalize path
    file = os.path.normpath(file.replace("..", "")).replace("\\", "/")
    if file[0] == "/":
        file = file[1:]

    # Get microdl_map
    latest = get_latest_version()
    microdl_map: dict[str, str] = read_json(
        config.get_archive_root_dir()
        + f"/{_PLATFORM_MAPPING[platform - 1]}/package/"
        + ("%s.%s/microdl_map.json" % latest)
    )
    path = ("/micro/%s.%s/" % latest) + file
    result = model.DownloadInfoModel(
        url=path,
        size=0,
        checksums=model.ChecksumModel(
            md5="d41d8cd98f00b204e9800998ecf8427e",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ),
    )
    if file in microdl_map:
        static_path = config.get_static_dir() + path
        archive = microdl_map[file]
        if not os.path.isfile(static_path):
            with _MICRODL_LOCK:
                # starts at 12 due to "archive-root" prefix
                with zipfile.ZipFile(config.get_archive_root_dir() + archive[12:]) as z:
                    try:
                        with z.open(file, "r") as fs:
                            os.makedirs(os.path.dirname(static_path), exist_ok=True)
                            with open(static_path, "wb") as fd:
                                fd.write(fs.read())
                    except KeyError:
                        pass
        if os.path.isfile(static_path):
            result.size, result.checksums.md5, result.checksums.sha256 = get_file_info(static_path)
    return result
