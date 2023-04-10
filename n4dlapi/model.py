import pydantic

from . import config


class VersionModel(pydantic.BaseModel):
    major: int
    minor: int


class PublicInfoModel(pydantic.BaseModel):
    publicApi: bool
    dlapiVersion: VersionModel
    serveTimeLimit: int
    gameVersion: str
    application: dict[str, str]
