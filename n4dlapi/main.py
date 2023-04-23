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

import fastapi
import fastapi.staticfiles

from . import config
from . import file
from . import model

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


@app.post(
    "/api/v1/batch",
    dependencies=[fastapi.Depends(verify_api_access)],
    response_model=list[model.BatchDownloadInfoModel],
    responses={404: {"model": model.ErrorResponseModel}},
)
async def batch_api(request: fastapi.Request, param: model.BatchDownloadRequestModel):
    """
    Get all download links of package IDs for specific package type.
    """
    downloads = file.get_batch_list(int(param.package_type), int(param.platform), param.exclude)
    if downloads is None:
        return fastapi.responses.JSONResponse(model.ErrorResponseModel(detail="Package type not found").dict(), 404)

    for download in downloads:
        download.url = str(request.url_for("archive-root", path=download.url))
    return downloads


@app.post(
    "/api/v1/download",
    dependencies=[fastapi.Depends(verify_api_access)],
    response_model=list[model.DownloadInfoModel],
    responses={404: {"model": model.ErrorResponseModel}},
)
async def download_api(request: fastapi.Request, param: model.DownlodaRequestModel):
    """
    Get download links for specific package type and package id.
    """
    downloads = file.get_single_package(int(param.package_type), param.package_id, int(param.platform))
    if downloads is None:
        return fastapi.responses.JSONResponse(model.ErrorResponseModel(detail="Package not found").dict(), 404)

    for download in downloads:
        download.url = str(request.url_for("archive-root", path=download.url))
    return downloads


@app.get(
    "/api/v1/getdb/{name}",
    dependencies=[fastapi.Depends(verify_api_access)],
    response_class=fastapi.responses.Response,
    responses={200: {"content": {"application/vnd.sqlite3": {}}}, 404: {"model": model.ErrorResponseModel}},
)
async def getdb_api(name: str):
    """
    Get decrypted database file.
    """
    db = file.get_database_file(name)
    if db is None:
        return fastapi.responses.JSONResponse(model.ErrorResponseModel(detail="Database not found").dict(), 404)

    return fastapi.responses.Response(
        db, media_type="application/vnd.sqlite3", headers={"Content-Disposition": f'attachment; filename="{name}.db_"'}
    )


@app.post(
    "/api/v1/getfile",
    dependencies=[fastapi.Depends(verify_api_access)],
    response_model=list[model.DownloadInfoModel],
    responses={404: {"model": model.ErrorResponseModel}},
)
async def getfile_api(request: fastapi.Request, param: model.MicroDownloadRequestModel):
    """
    Get single file from package type 4 a.k.a. micro download.
    """
    downloads = [file.get_microdl_file(p, int(param.platform)) for p in param.files]
    for download in downloads:
        download.url = str(request.url_for("static", path=download.url))
    return downloads


@app.get("/api/v1/release_info", dependencies=[fastapi.Depends(verify_api_access)])
async def release_info_api() -> dict[str, str]:
    """
    Get available `release_info` keys.
    """
    return file.get_release_info()
