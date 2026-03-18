from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ..config import get_settings
from ..dependencies import require_admin_request

router = APIRouter(tags=["console"])


def _admin_redirect(request: Request) -> RedirectResponse:
    require_admin_request(request)
    settings = get_settings()
    return RedirectResponse(url=f"{settings.web_base_url.rstrip('/')}/admin/", status_code=307)


@router.get("/console", include_in_schema=False)
def console_root(request: Request) -> RedirectResponse:
    return _admin_redirect(request)


@router.get("/console/", include_in_schema=False)
def console_page(request: Request) -> RedirectResponse:
    return _admin_redirect(request)


@router.get("/admin", include_in_schema=False)
def admin_root(request: Request) -> RedirectResponse:
    return _admin_redirect(request)


@router.get("/admin/", include_in_schema=False)
def admin_page(request: Request) -> RedirectResponse:
    return _admin_redirect(request)
