"""Web routes for cluster viewing."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.models.database import Cluster
from src.services.clustering import get_clustering_service

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/clusters", response_class=HTMLResponse)
async def clusters_page(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Clusters list page.

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

    # Get clusters
    stmt = select(Cluster).order_by(Cluster.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    clusters = result.scalars().all()

    # Get prompt counts
    from src.models.database import ClusterAssignment

    clusters_with_counts = []
    for cluster in clusters:
        count_stmt = select(func.count(ClusterAssignment.id)).where(
            ClusterAssignment.cluster_id == cluster.id
        )
        count_result = await db.execute(count_stmt)
        prompt_count = count_result.scalar() or 0

        # Get a sample prompt from this cluster
        from src.models.database import Prompt
        
        sample_prompt = None
        if prompt_count > 0:
            assignment_stmt = select(ClusterAssignment.prompt_id).where(
                ClusterAssignment.cluster_id == cluster.id
            ).limit(1)
            assignment_result = await db.execute(assignment_stmt)
            assignment = assignment_result.scalar_one_or_none()
            if assignment:
                prompt = await db.get(Prompt, assignment)
                if prompt:
                    sample_prompt = prompt.content[:100] + "..." if len(prompt.content) > 100 else prompt.content

        cluster_dict = {
            "id": str(cluster.id),
            "name": cluster.name,
            "prompt_count": prompt_count,
            "confidence_score": cluster.confidence_score,
            "created_at": cluster.created_at,
            "sample_prompt": sample_prompt or "No prompts",
        }
        clusters_with_counts.append(cluster_dict)

    # Get total count
    total_stmt = select(func.count(Cluster.id))
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    return templates.TemplateResponse(
        "clusters.html",
        {
            "request": request,
            "clusters": clusters_with_counts,
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@router.get("/clusters/{cluster_id}", response_class=HTMLResponse)
async def cluster_detail_page(
    request: Request,
    cluster_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Cluster detail page.

    Args:
        request: FastAPI request
        cluster_id: Cluster ID
        db: Database session

    Returns:
        HTML response
    """
    clustering_service = get_clustering_service(db)
    prompts = await clustering_service.get_cluster_prompts(cluster_id)

    cluster = await db.get(Cluster, cluster_id)
    if not cluster:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": "Cluster not found"},
            status_code=404,
        )

    return templates.TemplateResponse(
        "cluster_detail.html",
        {
            "request": request,
            "cluster": {
                "id": str(cluster.id),
                "name": cluster.name,
                "confidence_score": cluster.confidence_score,
                "created_at": cluster.created_at,
            },
            "prompts": [
                {
                    "id": str(p.id),
                    "content": p.content,  # Show full content
                    "created_at": p.created_at,
                }
                for p in prompts
            ],
        },
    )

