"""Web routes for dataset ingestion."""

from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


async def run_ingestion_background():
    """Background task runner that creates its own session."""
    from src.api.dependencies import get_session_factory
    from src.workers.dataset_ingestion import DatasetIngestionWorker
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        worker = DatasetIngestionWorker(db)
        await worker.ingest_all()


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
async def ingest_dataset_endpoint(background_tasks: BackgroundTasks):
    """
    Trigger dataset ingestion asynchronously in the background.

    Args:
        background_tasks: FastAPI background tasks

    Returns:
        Ingestion acceptance message
    """
    background_tasks.add_task(run_ingestion_background)
    return {
        "status": "accepted",
        "message": "Dataset ingestion started in the background"
    }

