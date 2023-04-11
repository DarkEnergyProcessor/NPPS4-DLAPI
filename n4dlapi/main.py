import fastapi
import fastapi.staticfiles

from . import config
from . import file
from . import model

from typing import Annotated

N4DLAPI_MAJOR_VERSION = 1
N4DLAPI_MINOR_VERSION = 0

config.init()

app = fastapi.FastAPI()
app.mount("/archive-root", fastapi.staticfiles.StaticFiles(directory=config.get_archive_root_dir()), "archive-root")
app.mount("/static", fastapi.staticfiles.StaticFiles(directory=config.get_static_dir()), "static")


def verify_api_access(request: fastapi.Request):
    if not config.is_accessible(request.url.path, request.headers.get("DLAPI-Shared-Key")):
        raise fastapi.HTTPException(404, "Not found.")
    return True


@app.get("/api/publicinfo", dependencies=[fastapi.Depends(verify_api_access)])
async def public_info_api() -> model.PublicInfoModel:
    """
    Retrieve information about the DLAPI server.
    """
    return model.PublicInfoModel(
        publicApi=config.is_public_accessible(),
        dlapiVersion=model.VersionModel(major=N4DLAPI_MAJOR_VERSION, minor=N4DLAPI_MINOR_VERSION),
        # This reference implementation doesn't impose any time limit restriction.
        serveTimeLimit=0,
        gameVersion="%s.%s" % file.get_latest_version(),
        application={},
    )


@app.post("/api/v1/update", dependencies=[fastapi.Depends(verify_api_access)])
async def update_api(request: fastapi.Request, param: model.UpdateRequestModel) -> list[model.DownloadInfoModel]:
    """
    Get download links for update package to the latest version available.
    """
    downloads = file.get_update_file(param.version, int(param.platform))
    for download in downloads:
        download.url = str(request.url_for("archive-root", path=download.url))
    return downloads


@app.post("/api/v1/batch", dependencies=[fastapi.Depends(verify_api_access)])
async def batch_api(request: fastapi.Request, param: model.BatchDownloadRequestModel):
    """
    Get all download links of package IDs for specific package type.
    """
    downloads = file.get_batch_list(int(param.package_type), param.platform, param.exclude)
    if downloads is None:
        raise fastapi.HTTPException(404, "Package type not found")
    for download in downloads:
        download.url = str(request.url_for("archive-root", path=download.url))
    return downloads


@app.get("/api/v1/release_info", dependencies=[fastapi.Depends(verify_api_access)])
async def release_info_api() -> dict[str, str]:
    """
    Get available `release_info` keys.
    """
    return file.get_release_info()
