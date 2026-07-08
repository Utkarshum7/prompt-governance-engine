"""Generic Job Scheduler with a Task Registry for periodic governance tasks."""

import asyncio
from typing import Callable, Dict, List, Optional
from structlog import get_logger

logger = get_logger("ai.governance.scheduler")


class ScheduledJob:
    """Represents a scheduled job task definition."""

    def __init__(self, name: str, job_func: Callable, interval_seconds: int):
        self.name = name
        self.job_func = job_func
        self.interval_seconds = interval_seconds
        self.last_run: Optional[float] = None
        self.task: Optional[asyncio.Task] = None


class JobScheduler:
    """JobScheduler maintains a registry of periodic background tasks."""

    def __init__(self):
        self.registry: Dict[str, ScheduledJob] = {}
        self.running = False
        logger.info("Job Scheduler initialized")

    def register(self, name: str, job_func: Callable, interval_seconds: int):
        """
        Register a new periodic job task.

        Args:
            name: Unique name of the task
            job_func: Coroutine function to execute
            interval_seconds: Execution frequency in seconds
        """
        self.registry[name] = ScheduledJob(name, job_func, interval_seconds)
        logger.info("Task registered in scheduler", task_name=name, interval=interval_seconds)

    async def _run_job_loop(self, job: ScheduledJob):
        """Worker loop that executes a single task periodically."""
        # Initial boot sleep to prevent bottlenecking startup validation
        await asyncio.sleep(10)
        while self.running:
            try:
                logger.info("Scheduled task triggering execution", task_name=job.name)
                
                # Execute the job function (handling both async and sync callbacks)
                if asyncio.iscoroutinefunction(job.job_func):
                    await job.job_func()
                else:
                    job.job_func()
                    
                logger.info("Scheduled task completed successfully", task_name=job.name)
            except asyncio.CancelledError:
                logger.info("Scheduled task worker cancelled", task_name=job.name)
                break
            except Exception as e:
                logger.error("Scheduled task execution failed", task_name=job.name, error=str(e))
                
            await asyncio.sleep(job.interval_seconds)

    def start(self):
        """Start execution of all registered background jobs."""
        if self.running:
            return
        self.running = True
        logger.info("Starting background scheduled jobs...")
        for job in self.registry.values():
            job.task = asyncio.create_task(self._run_job_loop(job))

    async def stop(self):
        """Stop and cancel all running background jobs."""
        if not self.running:
            return
        self.running = False
        logger.info("Stopping background scheduled jobs...")
        for job in self.registry.values():
            if job.task:
                job.task.cancel()
                try:
                    await job.task
                except asyncio.CancelledError:
                    pass
                job.task = None
        logger.info("Scheduler background workers stopped successfully")


# Global JobScheduler instance
_scheduler: Optional[JobScheduler] = None


def get_job_scheduler() -> JobScheduler:
    """Get global JobScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler()
    return _scheduler


# Standard scheduled job callbacks

async def run_periodic_drift_detection():
    """Scheduled callback to scan clusters and run drift detection."""
    from src.api.dependencies import get_session_factory
    from src.services.drift_detection import get_drift_detection_service
    from src.models.database import Cluster, CanonicalTemplate
    from sqlalchemy import select
    
    logger.info("Scheduled Job: Running active cluster drift detection...")
    try:
        session_factory = get_session_factory()
        async with session_factory() as db:
            stmt = select(Cluster.id).join(CanonicalTemplate)
            result = await db.execute(stmt)
            cluster_ids = [row[0] for row in result.all()]
            
            if not cluster_ids:
                logger.info("Scheduled Job: No templates found for drift checks.")
                return
                
            drift_service = get_drift_detection_service(db)
            for cid in cluster_ids:
                analysis = await drift_service.detect_drift(cluster_id=cid)
                if analysis.get("has_drift"):
                    logger.warning(
                        "Scheduled Job: Drift detected in cluster template",
                        cluster_id=str(cid),
                        drift_score=analysis.get("drift_score"),
                    )
            await db.commit()
    except Exception as e:
        logger.error("Scheduled Job: Failed periodic drift detection", error=str(e))


async def run_periodic_evaluation_metrics():
    """Scheduled callback to compile system analytics."""
    from src.api.dependencies import get_session_factory
    from src.services.evaluation import EvaluationEngine
    
    logger.info("Scheduled Job: Compiling platform quality metrics...")
    try:
        session_factory = get_session_factory()
        async with session_factory() as db:
            eval_engine = EvaluationEngine(db)
            metrics = await eval_engine.get_system_wide_metrics()
            logger.info("Scheduled Job: Compiled System Metrics", **metrics)
    except Exception as e:
        logger.error("Scheduled Job: Failed compiling metrics", error=str(e))


async def run_periodic_cache_cleanup():
    """Scheduled callback for cache indexing/cleanup."""
    logger.info("Scheduled Job: Running cache indexing and memory garbage collection...")
    # Simulated memory and cache GC checks
    await asyncio.sleep(0.1)


async def run_periodic_dataset_refresh():
    """Scheduled callback to check for new dataset updates."""
    logger.info("Scheduled Job: Checking dataset directory for updates...")
    # Simulated dataset directory refresh
    await asyncio.sleep(0.1)
