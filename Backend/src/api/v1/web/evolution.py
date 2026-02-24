"""Web routes for evolution viewing."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.models.database import EvolutionEvent, PromptFamily

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/evolution", response_class=HTMLResponse)
async def evolution_page(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Evolution events page.

    Args:
        request: FastAPI request
        page: Page number
        page_size: Items per page
        db: Database session

    Returns:
        HTML response
    """
    from sqlalchemy import select, func

    offset = (page - 1) * page_size

    # Get events
    stmt = select(EvolutionEvent).order_by(EvolutionEvent.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    events = result.scalars().all()

    # Get total count
    total_stmt = select(func.count(EvolutionEvent.id))
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    events_data = [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "template_id": str(e.template_id),
            "previous_version": e.previous_version,
            "new_version": e.new_version,
            "change_reason": e.change_reason,
            "detected_by": e.detected_by,
            "created_at": e.created_at,
        }
        for e in events
    ]

    return templates.TemplateResponse(
        "evolution.html",
        {
            "request": request,
            "events": events_data,
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@router.get("/evolution/families", response_class=HTMLResponse)
async def families_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Prompt families page.

    Args:
        request: FastAPI request
        db: Database session

    Returns:
        HTML response
    """
    from sqlalchemy import select, func
    from src.models.database import FamilyClusterMapping

    stmt = select(PromptFamily).order_by(PromptFamily.created_at.desc())
    result = await db.execute(stmt)
    families = result.scalars().all()

    families_data = []
    for family in families:
        count_stmt = select(func.count(FamilyClusterMapping.id)).where(
            FamilyClusterMapping.family_id == family.id
        )
        count_result = await db.execute(count_stmt)
        cluster_count = count_result.scalar() or 0

        families_data.append(
            {
                "id": str(family.id),
                "name": family.name,
                "description": family.description,
                "parent_family_id": str(family.parent_family_id) if family.parent_family_id else None,
                "cluster_count": cluster_count,
                "created_at": family.created_at,
            }
        )

    return templates.TemplateResponse(
        "families.html",
        {
            "request": request,
            "families": families_data,
        },
    )

