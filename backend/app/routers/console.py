from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from ..config import get_settings

router = APIRouter(tags=["console"])


def _admin_redirect() -> RedirectResponse:
    settings = get_settings()
    return RedirectResponse(url=f"{settings.web_base_url.rstrip('/')}/admin/", status_code=307)


@router.get("/console", include_in_schema=False)
def console_root() -> RedirectResponse:
    return _admin_redirect()


@router.get("/console/", include_in_schema=False)
def console_page() -> RedirectResponse:
    return _admin_redirect()


@router.get("/admin", include_in_schema=False)
def admin_root() -> RedirectResponse:
    return _admin_redirect()


@router.get("/admin/", include_in_schema=False)
def admin_page() -> RedirectResponse:
    return _admin_redirect()
