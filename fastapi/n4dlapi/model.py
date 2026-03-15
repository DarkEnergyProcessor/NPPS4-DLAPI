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

import enum

import pydantic


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

    class Config:
        schema_extra = {
            "example": {
                "url": "http://localhost/download/0_0_59.4.zip",
                "size": 12345,
                "checksums": {
                    "md5": "d41d8cd98f00b204e9800998ecf8427e",
                    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                },
            }
        }


class DownloadUpdateModel(DownloadInfoModel):
    version: str

    class Config:
        schema_extra = {
            "example": {
                "url": "http://localhost/download/0_0_59.4.zip",
                "size": 12345,
                "checksums": {
                    "md5": "d41d8cd98f00b204e9800998ecf8427e",
                    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                },
                "version": "59.4",
            }
        }


class BatchDownloadInfoModel(DownloadInfoModel):
    packageId: int

    class Config:
        schema_extra = {
            "example": {
                "url": "http://localhost/download/4_1874_59.4.zip",
                "size": 12345,
                "packageId": 1874,
                "checksums": {
                    "md5": "d41d8cd98f00b204e9800998ecf8427e",
                    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                },
            }
        }


class UpdateRequestModel(pydantic.BaseModel):
    version: str
    platform: PlatformType

    class Config:
        schema_extra = {"example": {"version": "59.0", "platform": 2}}


class BatchDownloadRequestModel(pydantic.BaseModel):
    package_type: PackageType
    platform: PlatformType
    exclude: list[int] = []

    class Config:
        schema_extra = {"example": {"package_type": 4, "platform": 1, "exclude": [1874]}}


class DownlodaRequestModel(pydantic.BaseModel):
    package_type: PackageType
    package_id: int
    platform: PlatformType

    class Config:
        schema_extra = {"example": {"package_type": 0, "package_id": 0, "platform": 1}}


class MicroDownloadRequestModel(pydantic.BaseModel):
    files: list[str]
    platform: PlatformType


class ErrorResponseModel(pydantic.BaseModel):
    detail: str
