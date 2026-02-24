"""Web routes for template viewing."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.models.database import CanonicalTemplate, TemplateSlot

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/templates", response_class=HTMLResponse)
async def templates_page(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Templates list page.

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

    # Get templates
    stmt = select(CanonicalTemplate).order_by(CanonicalTemplate.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    templates_list = result.scalars().all()

    # Get total count
    total_stmt = select(func.count(CanonicalTemplate.id))
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    templates_data = [
        {
            "id": str(t.id),
            "cluster_id": str(t.cluster_id),
            "version": t.version,
            "template_content": t.template_content,
            "confidence_score": t.confidence_score,
            "created_at": t.created_at,
        }
        for t in templates_list
    ]

    return templates.TemplateResponse(
        "templates.html",
        {
            "request": request,
            "templates": templates_data,
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@router.get("/templates/{template_id}", response_class=HTMLResponse)
async def template_detail_page(
    request: Request,
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Template detail page.

    Args:
        request: FastAPI request
        template_id: Template ID
        db: Database session

    Returns:
        HTML response
    """
    template = await db.get(CanonicalTemplate, template_id)
    if not template:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": "Template not found"},
            status_code=404,
        )

    # Get template slots
    from sqlalchemy import select

    stmt = select(TemplateSlot).where(TemplateSlot.template_id == template_id)
    result = await db.execute(stmt)
    slots = result.scalars().all()

    return templates.TemplateResponse(
        "template_detail.html",
        {
            "request": request,
            "template": {
                "id": str(template.id),
                "cluster_id": str(template.cluster_id),
                "version": template.version,
                "template_content": template.template_content,
                "confidence_score": template.confidence_score,
                "created_at": template.created_at,
            },
            "slots": [
                {
                    "name": s.slot_name,
                    "type": s.slot_type,
                    "example_values": s.example_values,
                    "confidence": s.confidence_score,
                }
                for s in slots
            ],
        },
    )

