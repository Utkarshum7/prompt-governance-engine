"""Web routes for dataset ingestion."""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.workers.dataset_ingestion import DatasetIngestionWorker

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/ingest-dataset", response_class=HTMLResponse)
async def ingest_dataset_page(request):
    """
    Dataset ingestion page.

    Args:
        request: FastAPI request

    Returns:
        HTML response
    """
    return templates.TemplateResponse("ingest_dataset.html", {"request": request})


@router.post("/api/v1/dataset/ingest")
async def ingest_dataset_endpoint(db: AsyncSession = Depends(get_db)):
    """
    Trigger dataset ingestion.

    Args:
        db: Database session

    Returns:
        Ingestion result
    """
    worker = DatasetIngestionWorker(db)
    result = await worker.ingest_all()
    return result

