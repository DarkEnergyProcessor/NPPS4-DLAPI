import fastapi
import fastapi.staticfiles

from . import config
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
async def publicinfo_api() -> model.PublicInfoModel:
    return model.PublicInfoModel(
        publicApi=config.is_public_accessible(),
        dlapiVersion=model.VersionModel(major=N4DLAPI_MAJOR_VERSION, minor=N4DLAPI_MINOR_VERSION),
        # This reference implementation doesn't impose any time limit restriction.
        serveTimeLimit=0,
        gameVersion="59.4",
        application={},
    )
