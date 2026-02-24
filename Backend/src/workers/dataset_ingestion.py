"""Dataset ingestion worker for processing prompts from Dataset folder."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.clients.redis import RedisClient, get_redis_client
from src.models.database import Prompt
from src.services.dataset_reader import DatasetReader, get_dataset_reader
from src.services.embedding import EmbeddingService, get_embedding_service
from src.services.moderation import ModerationService, get_moderation_service
from src.utils.batch_processor import BatchProcessor, get_batch_processor

logger = get_logger(__name__)


class DatasetIngestionWorker:
    """Worker to ingest all prompts from Dataset folder."""

    def __init__(
        self,
        db: AsyncSession,
        dataset_reader: Optional[DatasetReader] = None,
        moderation_service: Optional[ModerationService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        redis_client: Optional[RedisClient] = None,
        batch_processor: Optional[BatchProcessor] = None,
    ):
        """
        Initialize dataset ingestion worker.

        Args:
            db: Database session
            dataset_reader: Optional DatasetReader instance
            moderation_service: Optional ModerationService instance
            embedding_service: Optional EmbeddingService instance
            redis_client: Optional RedisClient instance
            batch_processor: Optional BatchProcessor instance
        """
        self.db = db
        self.dataset_reader = dataset_reader or get_dataset_reader()
        self.moderation_service = moderation_service or get_moderation_service()
        self.embedding_service = embedding_service or get_embedding_service()
        self.redis_client = redis_client or get_redis_client()
        self.batch_processor = batch_processor or get_batch_processor()

        # Statistics
        self.stats = {
            "files_processed": 0,
            "files_failed": 0,
            "prompts_processed": 0,
            "prompts_rejected": 0,
            "prompts_accepted": 0,
            "errors": [],
        }

        logger.info("Dataset ingestion worker initialized")

    def _get_checkpoint_key(self, file_path: Path) -> str:
        """
        Generate checkpoint key for a file.

        Args:
            file_path: Path to file

        Returns:
            Checkpoint key
        """
        return f"checkpoint:ingestion:{file_path.name}:{file_path.stat().st_mtime}"

    async def _save_checkpoint(self, file_path: Path, last_processed: int):
        """
        Save ingestion checkpoint.

        Args:
            file_path: Path to file being processed
            last_processed: Number of prompts processed
        """
        checkpoint_key = self._get_checkpoint_key(file_path)
        checkpoint_data = {
            "file_path": str(file_path),
            "last_processed": last_processed,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.redis_client.set(checkpoint_key, checkpoint_data, ttl=24 * 60 * 60)  # 24 hours

    async def _get_checkpoint(self, file_path: Path) -> Optional[int]:
        """
        Get ingestion checkpoint.

        Args:
            file_path: Path to file

        Returns:
            Number of prompts already processed, or None if no checkpoint
        """
        checkpoint_key = self._get_checkpoint_key(file_path)
        checkpoint = await self.redis_client.get(checkpoint_key)
        if checkpoint:
            return checkpoint.get("last_processed")
        return None

    async def _process_prompt(
        self, prompt_content: str, file_path: Path, trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a single prompt through the pipeline.

        Args:
            prompt_content: Prompt content
            file_path: Source file path
            trace_id: Optional trace ID

        Returns:
            Processing result dictionary
        """
        prompt_id = str(uuid.uuid4())

        try:
            # Step 1: Moderation check
            moderation_result = await self.moderation_service.moderate(prompt_content, trace_id=trace_id)

            if moderation_result["flagged"]:
                logger.warning(
                    "Prompt rejected by moderation",
                    prompt_id=prompt_id,
                    file=str(file_path),
                    trace_id=trace_id,
                )
                self.stats["prompts_rejected"] += 1
                return {
                    "prompt_id": prompt_id,
                    "status": "rejected",
                    "reason": "moderation_failed",
                    "moderation_result": moderation_result,
                }

            # Step 2: Generate embedding
            embedding, embedding_metadata = await self.embedding_service.generate_embedding(
                prompt_content, trace_id=trace_id
            )

            # Step 3: Store prompt in database
            prompt = Prompt(
                id=uuid.UUID(prompt_id),
                content=prompt_content,
                moderation_status=moderation_result["status"],
                embedding_id=None,  # Will be stored in vector DB separately
            )

            self.db.add(prompt)
            await self.db.flush()

            logger.debug(
                "Prompt processed successfully",
                prompt_id=prompt_id,
                file=str(file_path),
                trace_id=trace_id,
            )

            self.stats["prompts_accepted"] += 1

            return {
                "prompt_id": prompt_id,
                "status": "accepted",
                "embedding_dimensions": len(embedding),
                "moderation_status": moderation_result["status"],
                "embedding_metadata": embedding_metadata,
            }

        except Exception as e:
            logger.error(
                "Error processing prompt",
                prompt_id=prompt_id,
                file=str(file_path),
                error=str(e),
                trace_id=trace_id,
            )
            self.stats["errors"].append(
                {
                    "prompt_id": prompt_id,
                    "file": str(file_path),
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            return {
                "prompt_id": prompt_id,
                "status": "error",
                "error": str(e),
            }

    async def _process_batch(
        self, prompts: List[tuple[str, Path]], trace_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of prompts.

        Args:
            prompts: List of (prompt_content, file_path) tuples
            trace_id: Optional trace ID

        Returns:
            List of processing results
        """
        results = []

        for prompt_content, file_path in prompts:
            result = await self._process_prompt(prompt_content, file_path, trace_id=trace_id)
            results.append(result)
            self.stats["prompts_processed"] += 1

        return results

    async def ingest_file(self, file_path: Path, skip_checkpoint: bool = False) -> Dict[str, Any]:
        """
        Ingest prompts from a single file.

        Args:
            file_path: Path to file
            skip_checkpoint: Whether to skip checkpoint check

        Returns:
            Ingestion result dictionary
        """
        logger.info("Starting file ingestion", file=str(file_path))

        try:
            # Check checkpoint
            last_processed = None
            if not skip_checkpoint:
                last_processed = await self._get_checkpoint(file_path)

            # Read prompts from file
            prompts_to_process = []
            prompt_count = 0

            for prompt_data in self.dataset_reader.read_file(file_path):
                # Extract prompt content
                prompt_content = self.dataset_reader._extract_prompt_content(prompt_data)

                if not prompt_content:
                    logger.warning("Could not extract prompt content", data=prompt_data)
                    continue

                prompt_count += 1

                # Skip if already processed (checkpoint)
                if last_processed and prompt_count <= last_processed:
                    continue

                prompts_to_process.append((prompt_content, file_path))

            # Process prompts in batches
            if prompts_to_process:
                batches = self.batch_processor.chunk(prompts_to_process)

                for batch_num, batch in enumerate(batches, 1):
                    logger.debug(
                        "Processing batch",
                        file=str(file_path),
                        batch_num=batch_num,
                        batch_size=len(batch),
                    )

                    await self._process_batch(batch)

                    # Save checkpoint after each batch
                    await self._save_checkpoint(file_path, prompt_count)

            # Commit database changes
            await self.db.commit()

            self.stats["files_processed"] += 1

            logger.info(
                "File ingestion completed",
                file=str(file_path),
                prompts_processed=len(prompts_to_process),
            )

            return {
                "file": str(file_path),
                "status": "success",
                "prompts_processed": len(prompts_to_process),
                "total_prompts": prompt_count,
            }

        except Exception as e:
            logger.error("File ingestion failed", file=str(file_path), error=str(e))
            self.stats["files_failed"] += 1
            self.stats["errors"].append(
                {
                    "file": str(file_path),
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            await self.db.rollback()
            return {
                "file": str(file_path),
                "status": "failed",
                "error": str(e),
            }

    async def ingest_all(self) -> Dict[str, Any]:
        """
        Ingest all prompts from all files in Dataset folder.

        Returns:
            Ingestion summary dictionary
        """
        logger.info("Starting dataset ingestion")

        files = self.dataset_reader.list_files()

        if not files:
            logger.warning("No dataset files found")
            return {
                "status": "completed",
                "message": "No files found",
                "stats": self.stats,
            }

        logger.info("Found dataset files", count=len(files))

        # Process each file
        for file_path in files:
            await self.ingest_file(file_path)

        # Final commit
        await self.db.commit()

        logger.info("Dataset ingestion completed", stats=self.stats)

        # Get cluster and template counts
        from src.models.database import Cluster, CanonicalTemplate
        from sqlalchemy import select, func
        
        cluster_count_stmt = select(func.count(Cluster.id))
        cluster_result = await self.db.execute(cluster_count_stmt)
        cluster_count = cluster_result.scalar() or 0
        
        template_count_stmt = select(func.count(CanonicalTemplate.id))
        template_result = await self.db.execute(template_count_stmt)
        template_count = template_result.scalar() or 0
        
        return {
            "status": "completed",
            "stats": self.stats,
            "summary": {
                "files_processed": self.stats["files_processed"],
                "files_failed": self.stats["files_failed"],
                "prompts_processed": self.stats["prompts_processed"],
                "prompts_accepted": self.stats["prompts_accepted"],
                "prompts_rejected": self.stats["prompts_rejected"],
                "clusters_created": cluster_count,
                "templates_extracted": template_count,
                "error_count": len(self.stats["errors"]),
            },
        }

