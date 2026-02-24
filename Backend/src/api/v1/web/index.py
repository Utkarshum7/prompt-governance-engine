"""Home/dashboard page."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.api.dependencies import get_db
from src.models.database import Cluster, CanonicalTemplate, Prompt

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Home/dashboard page.

    Args:
        request: FastAPI request
        db: Database session

    Returns:
        HTML response
    """
    try:
        # Get basic stats
        cluster_count_stmt = select(func.count(Cluster.id))
        cluster_result = await db.execute(cluster_count_stmt)
        cluster_count = cluster_result.scalar() or 0

        template_count_stmt = select(func.count(CanonicalTemplate.id))
        template_result = await db.execute(template_count_stmt)
        template_count = template_result.scalar() or 0

        prompt_count_stmt = select(func.count(Prompt.id))
        prompt_result = await db.execute(prompt_count_stmt)
        prompt_count = prompt_result.scalar() or 0

        return templates.TemplateResponse(
            "index.html",
            {"request": request},
        )

    except Exception as e:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "stats": {"clusters": 0, "templates": 0, "prompts": 0}, "error": str(e)},
        )

