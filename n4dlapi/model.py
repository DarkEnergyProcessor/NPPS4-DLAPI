import enum

import pydantic

from . import config

from typing import Literal


class PlatformType(enum.IntEnum):
    """
    1. iOS
    2. Android
    """

    IOS = 1
    ANDROID = 2


class PackageType(enum.IntEnum):
    """
    0. Bootstrap
    1. Live
    2. Scenario
    3. Subscenario
    4. Micro
    5. Event Scenario
    6. Multi Unit Scenario
    """

    BOOTSTRAP = 0
    LIVE = 1
    SCENARIO = 2
    SUBSCENARIO = 3
    MICRO = 4
    EVENT_SCENARIO = 5
    MULTI_UNIT_SCENARIO = 6


class VersionModel(pydantic.BaseModel):
    major: int
    minor: int


class PublicInfoModel(pydantic.BaseModel):
    publicApi: bool
    dlapiVersion: VersionModel
    serveTimeLimit: int
    gameVersion: str
    application: dict[str, str]


class ChecksumModel(pydantic.BaseModel):
    md5: str
    sha256: str


class DownloadInfoModel(pydantic.BaseModel):
    url: str
    size: int
    checksums: ChecksumModel


class UpdateRequestModel(pydantic.BaseModel):
    version: str
    platform: PlatformType


class BatchDownloadRequestModel(pydantic.BaseModel):
    package_type: PackageType
    platform: PlatformType
    exclude: list[int] = []
