# Script to download your own local copy of SIF game data for private server.
#
# Copyright (c) 2023 Dark Energy Processor
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
import dataclasses
import hashlib
import http.client
import itertools
import json
import os
import pickle
import shutil
import time
import urllib.parse
import zipfile

from typing import Any


NEED_DLAPI_VERSION = (1, 1)


@dataclasses.dataclass
class DownloadChecksum:
    md5: str
    sha256: str


@dataclasses.dataclass
class DownloadInfo:
    url: str
    size: int
    checksums: DownloadChecksum


@dataclasses.dataclass
class DownloadUpdateInfo(DownloadInfo):
    version: str


@dataclasses.dataclass
class DownloadPackageInfo(DownloadInfo):
    package_id: int


@dataclasses.dataclass
class UpdateInfo:
    update: list[DownloadUpdateInfo]
    version: str
    expire: int


@dataclasses.dataclass
class PackageInfo:
    update: list[DownloadPackageInfo]
    version: str
    expire: int


class CloneDownloadError(RuntimeError):
    pass


def get_port_by_parseresult(parse: urllib.parse.ParseResult):
    if parse.scheme == "https":
        return parse.port or 443
    elif parse.scheme == "http":
        return parse.port or 80
    else:
        raise ValueError(f"Unknown schema '{parse.scheme}'")


def new_http_client(parse: urllib.parse.ParseResult):
    if parse.hostname is None:
        raise ValueError(f"Unknown hostname")
    if parse.scheme == "https":
        cls = http.client.HTTPSConnection
    elif parse.scheme == "http":
        cls = http.client.HTTPConnection
    else:
        raise ValueError(f"Unknown schema '{parse.scheme}'")

    return cls(parse.hostname, get_port_by_parseresult(parse), timeout=30)


_dl_http_client: http.client.HTTPSConnection | http.client.HTTPConnection | None = None
_api_http_client: http.client.HTTPSConnection | http.client.HTTPConnection | None = None


def update_http_client(
    parse: urllib.parse.ParseResult, handle: http.client.HTTPSConnection | http.client.HTTPConnection | None
):
    if (
        handle is None
        or handle.host != parse.hostname
        or handle.port != get_port_by_parseresult(parse)
        or (isinstance(handle, http.client.HTTPSConnection) and parse.scheme == "http")
        or (isinstance(handle, http.client.HTTPConnection) and parse.scheme == "https")
    ):
        if handle is not None:
            handle.close()
        return new_http_client(parse)
    return handle


def get_paths_from_parseresult(parse: urllib.parse.ParseResult):
    # Had to reinvent the wheel
    s: list[str] = [parse.path]

    if parse.params:
        s.append(";")
        s.append(parse.params)

    if parse.query:
        s.append("?")
        s.append(parse.query)

    return "".join(s)


def download_file_notry(url: str, /, *, redircount: int = 0) -> bytes:
    global _dl_http_client
    parse = urllib.parse.urlparse(url)

    _dl_http_client = update_http_client(parse, _dl_http_client)
    _dl_http_client.request("GET", get_paths_from_parseresult(parse))
    response = _dl_http_client.getresponse()
    code = response.getcode()

    if code in (301, 302, 303, 307, 308):
        # Redirect
        if redircount > 5:
            raise RuntimeError(f"'{url}' does not properly setup its redirect")
        newloc = response.getheader("Location")
        if newloc is None:
            raise RuntimeError(f"'{url}' says redirect but no Location header")
        newparse = urllib.parse.urlparse(newloc)
        if not newparse.scheme:
            newparse = newparse._replace(scheme=parse.scheme)
        if not newparse.netloc:
            newparse = newparse._replace(netloc=parse.netloc)
        return download_file_notry(newparse.geturl(), redircount=redircount + 1)
    if code != 200:
        raise CloneDownloadError(f"'{url}' returned {code}")

    return response.read()


def download_file(url: str, /):
    retry = 0
    while True:
        try:
            return download_file_notry(url)
        except Exception as e:
            retry = retry + 1
            if isinstance(e, CloneDownloadError) or retry >= 25:
                raise e from None


def call_api_notry(
    api_urlpath: str, shared_key: str, endpoint: str, request_data: dict[str, Any] | list[Any] | None = None, /
):
    global _api_http_client
    parse_api = urllib.parse.urlparse(api_urlpath)
    parse = parse_api._replace(
        path=(parse_api.path if parse_api.path[-1] == "/" else parse_api.path[:-1])
        + (endpoint[1:] if endpoint[0] == "/" else endpoint)
    )

    _api_http_client = update_http_client(parse, _api_http_client)
    header = {}
    if shared_key:
        header["DLAPI-Shared-Key"] = urllib.parse.quote(shared_key)
    if request_data is not None:
        header["Content-Type"] = "application/json"
    _api_http_client.request(
        "GET" if request_data is None else "POST", parse.path, json.dumps(request_data).encode("UTF-8"), header
    )

    response = _api_http_client.getresponse()
    code = response.getcode()
    if code != 200:
        raise CloneDownloadError(f"'{parse.geturl()}' returned {code}")

    return json.loads(response.read())


def call_api(
    api_urlpath: str, shared_key: str, endpoint: str, request_data: dict[str, Any] | list[Any] | None = None, /
):
    retry = 0
    while True:
        try:
            return call_api_notry(api_urlpath, shared_key, endpoint, request_data)
        except Exception as e:
            retry = retry + 1
            if isinstance(e, CloneDownloadError) or retry >= 25:
                raise e from None


def verify_hash(data: bytes, checksums: DownloadChecksum):
    md5 = hashlib.md5(data, usedforsecurity=False).hexdigest()
    sha256 = hashlib.sha256(data, usedforsecurity=False).hexdigest()
    if md5 != checksums.md5:
        raise RuntimeError(f"MD5 does not match. Expected {checksums.md5} got {md5}")
    if sha256 != checksums.sha256:
        raise RuntimeError(f"SHA256 does not match. Expected {checksums.sha256} got {sha256}")


def read_json_file(path: str):
    with open(path, "r", encoding="UTF-8") as f:
        return json.load(f)


def write_json_file(path: str, data):
    with open(path, "w", encoding="UTF-8") as f:
        json.dump(data, f)


def to_sifversion(ver: str):
    s = ver.split(".", 1)
    return int(s[0]), int(s[1])


def continue_update(path: str):
    update_pickle = path + "/update.pickle"
    if not os.path.exists(update_pickle):
        return
    with open(update_pickle, "rb") as f:
        update_info: UpdateInfo = pickle.load(f)
        if int(time.time()) >= update_info.expire:
            raise RuntimeError(f"Links expired. Please delete {update_pickle} and try again!")

    print("Starting download update:", path)
    # Separate download links by versions
    by_versions: dict[str, list[DownloadUpdateInfo]] = {}
    for info in update_info.update:
        by_versions.setdefault(info.version, []).append(info)

    # Iterate versions
    for version, updates in by_versions.items():
        version_path = f"{path}/update/{version}"
        info_file = version_path + "/info.json"
        os.makedirs(version_path, exist_ok=True)

        if not os.path.exists(info_file):
            # We assume SIF server provide the files in-order.
            i = 1
            update_count = len(updates)
            infotuple: list[tuple[str, int]] = []
            archives: list[str] = []

            for update in updates:
                archive_dest = f"{version_path}/{i}.zip"

                if not os.path.exists(archive_dest):
                    print(f"Downloading update file {i}/{update_count}", archive_dest)
                    archive = download_file(update.url)
                    verify_hash(archive, update.checksums)
                    with open(archive_dest, "wb") as f:
                        f.write(archive)
                    archives.append(archive_dest)

                infotuple.append((f"{i}.zip", update.size))
                i = i + 1
            write_json_file(info_file, dict(infotuple))

    # Add new version list
    versionlist_path = f"{path}/update/info.json"
    if os.path.exists(versionlist_path):
        versionlist: list[str] = read_json_file(versionlist_path)
    else:
        versionlist = []
    if update_info.version not in versionlist:
        versionlist.append(update_info.version)
        write_json_file(versionlist_path, versionlist)

    # Remove temporary update file
    os.remove(update_pickle)


def prepare_update(path: str, target_client: str, data: list[dict], expire: int):
    update_info = UpdateInfo(
        version=target_client,
        update=[
            DownloadUpdateInfo(
                url=d["url"],
                size=d["size"],
                checksums=DownloadChecksum(md5=d["checksums"]["md5"], sha256=d["checksums"]["sha256"]),
                version=d["version"],
            )
            for d in data
        ],
        expire=expire,
    )
    update_pickle = path + "/update.pickle"
    with open(update_pickle, "wb") as f:
        pickle.dump(update_info, f)


def move_all_batches(files: list[tuple[str, int]], dest: str):
    os.makedirs(dest, exist_ok=True)

    info_json: dict[str, int] = {}
    i = 1
    for file, size in files:
        file_dest = f"{dest}/{i}.zip"
        shutil.copyfile(file, file_dest)
        info_json[f"{i}.zip"] = size
        i = i + 1

    # Write JSON
    write_json_file(f"{dest}/info.json", info_json)

    # Delete source files
    for file, size in files:
        os.remove(file)


def continue_batch_download(path: str, package_type: int):
    update_pickle = f"{path}/package_{package_type}.pickle"
    if not os.path.exists(update_pickle):
        return
    with open(update_pickle, "rb") as f:
        package_info: PackageInfo = pickle.load(f)
        if int(time.time()) >= package_info.expire:
            raise RuntimeError(f"Links expired. Please delete {update_pickle} and try again!")

    current_package_path = f"{path}/{package_info.version}/{package_type}"
    os.makedirs(current_package_path, exist_ok=True)
    print("Starting batch download:", package_type, path)

    by_package_id: dict[int, list[DownloadPackageInfo]] = {}
    for info in package_info.update:
        by_package_id.setdefault(info.package_id, []).append(info)

    # Download files
    for package_id, updates in by_package_id.items():
        target_path = f"{current_package_path}/{package_id}"
        info_file = target_path + "/info.json"
        os.makedirs(target_path, exist_ok=True)

        if not os.path.exists(info_file):
            # Actually download file instead of skipping them
            i = 1
            update_count = len(updates)
            infotuple: list[tuple[str, int]] = []
            archives: list[str] = []

            for update in updates:
                archive_dest = f"{target_path}/{i}.zip"

                if not os.path.exists(archive_dest):
                    print(f"Downloading package {package_type}/{package_id} file {i}/{update_count}", archive_dest)
                    archive = download_file(update.url)
                    verify_hash(archive, update.checksums)
                    with open(archive_dest, "wb") as f:
                        f.write(archive)
                    archives.append(archive_dest)

                infotuple.append((f"{i}.zip", update.size))
                i = i + 1
            write_json_file(info_file, dict(infotuple))

    # Write info.json
    print("Building info.json for package type", package_type)
    write_json_file(f"{current_package_path}/info.json", sorted(by_package_id.keys()))
    # Remove temporary update file
    os.remove(update_pickle)


def prepare_batch_download(path: str, target_client: str, package_type: int, data: list[dict], expire: int):
    update_info = PackageInfo(
        update=[
            DownloadPackageInfo(
                url=d["url"],
                size=d["size"],
                checksums=DownloadChecksum(md5=d["checksums"]["md5"], sha256=d["checksums"]["sha256"]),
                package_id=d["packageId"],
            )
            for d in data
        ],
        version=target_client,
        expire=expire,
    )
    update_pickle = f"{path}/package_{package_type}.pickle"
    with open(update_pickle, "wb") as f:
        pickle.dump(update_info, f)


def continue_download(root: str, oses: list[str]):
    print("Resuming incomplete downloads.")
    for sif_os in oses:
        continue_update(f"{root}/{sif_os}")
    for sif_os, pkg_type in itertools.product(oses, range(0, 7)):
        continue_batch_download(f"{root}/{sif_os}/package", pkg_type)


def make_microdl_map(package_dir: str):
    info_json: list[int] = read_json_file(f"{package_dir}/4/info.json")
    file_map: dict[str, str] = {}

    # Iterate
    for id in info_json:
        archive_list: dict[str, int] = read_json_file(f"{package_dir}/4/{id}/info.json")
        for i in range(1, len(archive_list) + 1):
            archive_name = f"{package_dir}/4/{id}/{i}.zip"
            print("Scanning", archive_name)
            with zipfile.ZipFile(archive_name) as z:
                for info in z.infolist():
                    file_map[info.filename] = archive_name

    # Write microdl_map.json
    print("Writing microdl_map.json")
    write_json_file(f"{package_dir}/microdl_map.json", file_map)


def get_expiry_time_string(dt: int):
    if dt == 0:
        return "no expiration"

    seconds = dt % 60
    minutes = dt // 60 % 60
    hours = dt // 3600

    result: list[str] = []
    if hours == 1:
        result.append("1 hour")
    elif hours > 1:
        result.append(f"{hours} hours")

    if minutes == 1:
        result.append("1 minute")
    elif minutes > 1:
        result.append(f"{minutes} minutes")

    if seconds == 1:
        result.append("1 second")
    elif seconds > 1:
        result.append(f"{seconds} seconds")

    return "".join(result)


def get_expiry_time(dt: int):
    if dt == 0:
        return pow(2, 53)

    return int(time.time()) + dt


def remap_os(os: str):
    if os == "Android":
        return 2
    elif os == "iOS":
        return 1
    else:
        raise RuntimeError(f"Unknown OS '{os}'")


def get_latest_version(root: str):
    for v in ("iOS", "Android"):
        read_path = f"{root}/{v}/package/info.json"
        if os.path.isfile(read_path):
            update_info: list[tuple[int, int]] = list(map(to_sifversion, read_json_file(read_path)))
            return update_info[-1]

    return None


def archive_main(root: str, apiurl: str, shared_key: str, oses: list[str], base_version: tuple[int, int]):
    for sif_os in oses:
        os.makedirs(f"{root}/{sif_os}/package", exist_ok=True)
    continue_download(root, oses)

    # Call public info API
    print("Calling public info API...")
    public_info: dict[str, Any] = call_api(apiurl, shared_key, "api/publicinfo")
    target_client: tuple[int, int] = to_sifversion(public_info["gameVersion"])
    target_client_str = "%d.%d" % target_client
    serve_time_limit: int = public_info["serveTimeLimit"]
    version = (int(public_info["dlapiVersion"]["major"]), int(public_info["dlapiVersion"]["minor"]))

    print()
    print("Mirror information")
    print("Base URL:", apiurl)
    print("Version:", version)
    print("Latest Game Version:", target_client_str)
    print("Link Expiry Duration:", get_expiry_time_string(serve_time_limit))
    if "application" in public_info and public_info["application"]:
        print("Additional app-specific data:")
        for k, v in public_info["application"].items():
            print(f"* {k}:", v)

    if version[0] != NEED_DLAPI_VERSION[0] or NEED_DLAPI_VERSION[1] > version[1]:
        raise RuntimeError(f"Mirror only provides version {version} protocol, but {NEED_DLAPI_VERSION} is required!")

    os_package_combination = list(itertools.product(oses, range(0, 7)))

    # Get update
    latest_version = get_latest_version(root) or base_version
    if target_client > latest_version:
        for sif_os in oses:
            update_links: list[dict] = call_api(
                apiurl,
                shared_key,
                "api/v1/update",
                {"version": "%d.%d" % max(latest_version, base_version), "platform": remap_os(sif_os)},
            )
            prepare_update(f"{root}/{sif_os}", target_client_str, update_links, get_expiry_time(serve_time_limit))
        for sif_os in oses:
            continue_update(f"{root}/{sif_os}")

    # Get package
    for sif_os, pkg_type in os_package_combination:
        path = f"{root}/{sif_os}/package"
        info_path = f"{path}/{target_client}/{pkg_type}/info.json"
        if os.path.exists(info_path):
            exclude: list[int] = read_json_file(info_path)
        else:
            exclude = []
        batch_links: list[dict] = call_api(
            apiurl,
            shared_key,
            "api/v1/batch",
            {"package_type": pkg_type, "platform": remap_os(sif_os), "exclude": exclude},
        )
        if len(batch_links) > 0:
            prepare_batch_download(path, target_client_str, pkg_type, batch_links, get_expiry_time(serve_time_limit))
    for sif_os, pkg_type in os_package_combination:
        continue_batch_download(f"{root}/{sif_os}/package", pkg_type)
    for sif_os in oses:
        make_microdl_map(f"{root}/{sif_os}/package/{target_client_str}")

    for sif_os in oses:
        versionlist_path = f"{root}/{sif_os}/package/info.json"
        if os.path.exists(versionlist_path):
            versionlist: list[str] = read_json_file(versionlist_path)
        else:
            versionlist = []
        if target_client_str not in versionlist:
            versionlist.append(target_client_str)
            write_json_file(versionlist_path, versionlist)

    # Get release keys
    print("Downloading release_info.json keys")
    release_keys: dict[str, str] = call_api(apiurl, shared_key, "api/v1/release_info")
    write_json_file(f"{root}/release_info.json", release_keys)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", help="Where to store the mirrored files.")
    parser.add_argument(
        "mirror",
        help=f"URL to a site (with path) that talks with NPPS4 DLAPI v{NEED_DLAPI_VERSION[0]}.{NEED_DLAPI_VERSION[1]} protocol.",
    )
    parser.add_argument("--no-ios", help="Don't download iOS files.", action="store_true")
    parser.add_argument("--no-android", help="Don't download Android files.", action="store_true")
    parser.add_argument("--shared-key", help="Shared Key to communicate with the mirror server", default="")
    parser.add_argument(
        "--base-version",
        help='Specify base SIF version for update download (default "59.0").',
        default=(59, 0),
        type=to_sifversion,
    )
    args = parser.parse_args()

    oses: list[str] = []
    if not args.no_ios:
        oses.append("iOS")
    if not args.no_android:
        oses.append("Android")
    if not oses:
        raise RuntimeError("Nothing downloaded.")

    root: str = args.destination.replace("\\", "/")
    mirror: str = (args.mirror + "/") if args.mirror[-1] != "/" else args.mirror
    if not mirror.startswith("http://") and (not mirror.startswith("https://")):
        mirror = "https://" + mirror
    return archive_main(root[:-1] if root[-1] == "/" else root, mirror, args.shared_key, oses, args.base_version)


def add_lock():
    if not os.path.exists("inprogress.lock"):
        open("inprogress.lock", "w").close()
        return True
    return False


def remove_lock():
    try:
        os.remove("inprogress.lock")
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    if add_lock():
        try:
            main()
        finally:
            remove_lock()
    else:
        print("An instance already running")
