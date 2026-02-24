"""Batch processing utilities for chunking and processing batches."""

from typing import Callable, List, Optional, TypeVar, Tuple

from structlog import get_logger

from src.config.settings import get_settings

logger = get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class BatchProcessor:
    """Utility for chunking and processing batches."""

    def __init__(self, batch_size: Optional[int] = None):
        """
        Initialize batch processor.

        Args:
            batch_size: Batch size for processing. If None, uses config default.
        """
        settings = get_settings()
        self.batch_size = batch_size or settings.app.processing.batch_size

        logger.info("Batch processor initialized", batch_size=self.batch_size)

    def chunk(self, items: List[T], batch_size: Optional[int] = None) -> List[List[T]]:
        """
        Chunk items into batches.

        Args:
            items: List of items to chunk
            batch_size: Optional batch size override

        Returns:
            List of batches
        """
        size = batch_size or self.batch_size
        batches = [items[i : i + size] for i in range(0, len(items), size)]
        logger.debug("Chunked items into batches", total_items=len(items), num_batches=len(batches))
        return batches

    async def process_batches(
        self,
        items: List[T],
        process_func: Callable[[List[T]], R],
        batch_size: Optional[int] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_error: Optional[Callable[[List[T], Exception], None]] = None,
    ) -> List[R]:
        """
        Process items in batches with error handling.

        Args:
            items: List of items to process
            process_func: Async function to process a batch
            batch_size: Optional batch size override
            on_progress: Optional callback for progress updates (current, total)
            on_error: Optional callback for error handling (batch, error)

        Returns:
            List of results from processing batches
        """
        batches = self.chunk(items, batch_size)
        results = []
        total_batches = len(batches)

        logger.info("Starting batch processing", total_items=len(items), total_batches=total_batches)

        for i, batch in enumerate(batches, 1):
            try:
                logger.debug("Processing batch", batch_num=i, batch_size=len(batch), total_batches=total_batches)
                result = await process_func(batch)
                results.append(result)

                if on_progress:
                    on_progress(i, total_batches)

            except Exception as e:
                logger.error(
                    "Batch processing error",
                    batch_num=i,
                    batch_size=len(batch),
                    error=str(e),
                )

                if on_error:
                    on_error(batch, e)
                else:
                    # Default: log and continue
                    logger.warning("Skipping failed batch", batch_num=i)

        logger.info(
            "Batch processing completed",
            total_batches=total_batches,
            successful=len(results),
            failed=total_batches - len(results),
        )

        return results

    async def process_batches_with_results(
        self,
        items: List[T],
        process_func: Callable[[List[T]], List[R]],
        batch_size: Optional[int] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_error: Optional[Callable[[List[T], Exception], None]] = None,
    ) -> List[R]:
        """
        Process items in batches and flatten results.

        Args:
            items: List of items to process
            process_func: Async function to process a batch (returns list of results)
            batch_size: Optional batch size override
            on_progress: Optional callback for progress updates (current, total)
            on_error: Optional callback for error handling (batch, error)

        Returns:
            Flattened list of all results
        """
        batch_results = await self.process_batches(
            items, process_func, batch_size, on_progress, on_error
        )

        # Flatten results
        flattened_results = []
        for batch_result in batch_results:
            if isinstance(batch_result, list):
                flattened_results.extend(batch_result)
            else:
                flattened_results.append(batch_result)

        return flattened_results


def get_batch_processor(batch_size: Optional[int] = None) -> BatchProcessor:
    """
    Get batch processor instance.

    Args:
        batch_size: Optional batch size override

    Returns:
        BatchProcessor instance
    """
    return BatchProcessor(batch_size=batch_size)

