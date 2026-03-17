from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(tags=["console"])

_STATIC_ROOT = Path(__file__).resolve().parent.parent / "static" / "console"
_ADMIN_FILE = _STATIC_ROOT / "admin.html"


@router.get("/console", include_in_schema=False)
def console_root() -> RedirectResponse:
    return RedirectResponse(url="/admin/", status_code=307)


@router.get("/console/", include_in_schema=False)
def console_page() -> RedirectResponse:
    return RedirectResponse(url="/admin/", status_code=307)


@router.get("/admin", include_in_schema=False)
def admin_root() -> RedirectResponse:
    return RedirectResponse(url="/admin/", status_code=307)


@router.get("/admin/", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse(_ADMIN_FILE)
