"""Web routes for prompt ingestion."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/ingest-prompt", response_class=HTMLResponse)
async def ingest_prompt_page(request: Request):
    """
    Prompt ingestion form page.

    Args:
        request: FastAPI request

    Returns:
        HTML response
    """
    return templates.TemplateResponse("ingest_prompt.html", {"request": request})

