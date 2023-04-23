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

# tomli is bundled in Python 3.11 as tomllib
try:
    import tomllib
except ImportError:
    import tomli as tomllib

from typing import Any

main_public = True
shared_key = None
archive_root = "archive-root"
static_dir = "static"
api_publicness: dict[str, Any] = {}

EMPTY: dict[str, Any] = {}
REQUIRE_GENERATION = (1, 1)


def verify_dir(dir: str):
    if not os.path.isdir(dir):
        raise RuntimeError(f'"{dir}" does not point to valid directory')


def init():
    global archive_root, static_dir

    config_file = os.getenv("N4DLAPI_CONFIG_FILE", "config.toml")
    if os.path.isfile(config_file):
        with open(config_file, "rb") as f:
            toml = tomllib.load(f)
        load_toml(toml)
    else:
        load_defaults()
    # Verify paths
    verify_dir(archive_root)
    os.makedirs(static_dir, exist_ok=True)
    verify_dir(static_dir)
    # Normalize paths
    archive_root = os.path.normpath(archive_root)
    static_dir = os.path.normpath(static_dir)
    # Verify archive-root generation
    try:
        with open(f"{archive_root}/generation.json", "r", encoding="UTF-8", newline="") as f:
            argen_data = json.load(f)
            argen: tuple[int, int] = (argen_data["major"], argen_data["minor"])
    except Exception:
        argen = (1, 0)
    if argen < REQUIRE_GENERATION:
        raise RuntimeError(
            '"archive-root" generation is too old (' + ("%d.%d" % argen) + "). Forgot to run update script?"
        )
    elif argen[0] > REQUIRE_GENERATION[0]:
        raise RuntimeError('"archive-root" generation is too new (' + ("%d.%d" % argen) + ").")


def load_toml(toml: dict[str, Any]):
    global main_public, shared_key, archive_root, static_dir, api_publicness

    main_public = bool(toml["main"]["public"])
    shared_key = str(toml["main"]["shared_key"])
    if len(shared_key) == 0:
        shared_key = None
    archive_root = os.getenv("N4DLAPI_ARCHIVE_ROOT", str(toml["main"].get("archive_root", "archive-root")))
    static_dir = os.getenv("N4DLAPI_STATIC_DIR", str(toml["main"].get("static_dir", "static")))
    api_publicness = toml.get("api", {})


def load_defaults():
    global main_public, shared_key, archive_root, static_dir, api_publicness

    main_public = True
    shared_key = None
    archive_root = os.getenv("N4DLAPI_ARCHIVE_ROOT", "archive-root")
    static_dir = os.getenv("N4DLAPI_STATIC_DIR", "static")
    api_publicness = {}


def is_endpoint_accessible(endpoint: str):
    global main_public, api_publicness

    split_endpoint = (endpoint[1:] if endpoint[0] == "/" else endpoint).split("/")
    if split_endpoint[0] != "api":
        return False
    current = api_publicness
    for target in split_endpoint[1:]:
        current = current.get(target, EMPTY)
    return bool(current.get("public", main_public))


# Endpoint is "/api/..."
def is_accessible(endpoint: str, sk: str | None):
    global shared_key

    if shared_key is None:
        return True
    if is_endpoint_accessible(endpoint):
        return True
    return shared_key == sk


def is_public_accessible():
    global main_public
    return main_public


def get_archive_root_dir():
    global archive_root
    return archive_root


def get_static_dir():
    global static_dir
    return static_dir


__all__ = ["init", "is_accessible", "is_public_accessible", "get_archive_root_dir", "get_static_dir"]
