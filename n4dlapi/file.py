import hashlib
import json
import os

import natsort

from . import config
from . import model

from typing import Callable, TypeVar, Generic

_T = TypeVar("_T")

_PLATFORM_MAPPING = ["iOS", "Android"]


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
def hash_md5_file(file: str) -> str:
    with open(file, "rb") as f:
        md5 = hashlib.md5(usedforsecurity=False)
        while True:
            result = f.read(4096)
            if len(result) > 0:
                md5.update(result)
            if len(result) < 4096:
                break
        return md5.hexdigest()


@MemoizeByModTime
def hash_sha256_file(file: str) -> str:
    with open(file, "rb") as f:
        sha256 = hashlib.sha256(usedforsecurity=False)
        while True:
            result = f.read(4096)
            if len(result) > 0:
                sha256.update(result)
            if len(result) < 4096:
                break
        return sha256.hexdigest()


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
            download_data.append(
                model.DownloadInfoModel(
                    url=fullpath[archive_root_len:],
                    size=size,
                    checksums=model.ChecksumModel(md5=hash_md5_file(fullpath), sha256=hash_sha256_file(fullpath)),
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
    archive_root_len = len(config.get_archive_root_dir())

    if not os.path.isdir(path):
        # Not found
        print(path)
        return None

    result: list[model.BatchDownloadInfoModel] = []
    packages: list[int] = read_json(path + "/info.json")

    for package_id in sorted(set(packages).difference(exclude)):
        files: list[tuple[str, int]] = natsort.natsorted(
            read_json(f"{path}/{package_id}/info.json").items(), key=lambda x: x[0]
        )
        for file, size in files:
            fullpath = f"{path}/{package_id}/{file}"
            result.append(
                model.BatchDownloadInfoModel(
                    url=fullpath[archive_root_len:],
                    size=size,
                    checksums=model.ChecksumModel(md5=hash_md5_file(fullpath), sha256=hash_sha256_file(fullpath)),
                    packageId=package_id,
                )
            )

    return result
