from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(tags=["console"])

_STATIC_ROOT = Path(__file__).resolve().parent.parent / "static" / "console"
_INDEX_FILE = _STATIC_ROOT / "index.html"


@router.get("/console", include_in_schema=False)
def console_root() -> RedirectResponse:
    return RedirectResponse(url="/console/", status_code=307)


@router.get("/console/", include_in_schema=False)
def console_page() -> FileResponse:
    return FileResponse(_INDEX_FILE)
