"""AI Orchestrator that coordinates all AI prompt governance workflows."""

import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.clients.redis import get_redis_client
from src.services.decision_engine import get_decision_engine
from src.services.model_router import get_model_router
from src.services.embedding import get_embedding_service
from src.services.moderation import get_moderation_service
from src.services.clustering import get_clustering_service
from src.services.canonicalization import get_canonicalization_service
from src.services.drift_detection import get_drift_detection_service
from src.services.lineage import PromptLineageEngine
from src.services.evaluation import EvaluationEngine
from src.utils.events import log_ai_decision
from src.models.database import Prompt, Cluster, CanonicalTemplate

logger = get_logger("ai.governance.orchestrator")


class AIOrchestrator:
    """Unified Orchestrator coordinating AI Decision Engine, Router, Lineage, and Evaluation."""

    def __init__(self, db: AsyncSession):
        """Initialize AI Orchestrator with active database session."""
        self.db = db
        self.decision_engine = get_decision_engine()
        self.model_router = get_model_router()
        self.embedding_service = get_embedding_service()
        self.moderation_service = get_moderation_service()
        self.clustering_service = get_clustering_service(db)
        self.canonicalization_service = get_canonicalization_service(db)
        self.drift_service = get_drift_detection_service(db)
        self.lineage_engine = PromptLineageEngine(db)
        self.evaluation_engine = EvaluationEngine(db)

    async def ingest_prompt(self, content: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Coordinate full ingestion pipeline with Decision Engine analysis and telemetry logging.
        """
        start_time = time.time()
        req_id = trace_id or str(uuid.uuid4())

        try:
            logger.info("Orchestrator: Initiating prompt ingestion", request_id=req_id, content_len=len(content))

            # 1. Moderation Check
            moderation_result = await self.moderation_service.moderate(content, trace_id=req_id)
            if moderation_result.get("flagged"):
                log_ai_decision(
                    request_id=req_id,
                    selected_model="moderation-model",
                    routing_reason="content_flagged",
                    confidence_score=1.0,
                    latency=time.time() - start_time,
                )
                return {
                    "status": "rejected",
                    "reason": "moderation_failed",
                    "moderation_result": moderation_result,
                }

            # 2. Run AI Decision Engine
            decision = await self.decision_engine.analyze_prompt(content)

            # 3. Route and Generate Embedding
            routing_config = self.model_router.route_for_decision(decision)
            selected_embedding_model = routing_config["targets"][0]["model"]
            
            embedding, embedding_metadata = await self.embedding_service.generate_embedding(
                content, model=f"@{routing_config['targets'][0]['provider']}/{selected_embedding_model}", trace_id=req_id
            )

            # 4. Insert raw prompt record
            prompt_id = uuid.uuid4()
            prompt = Prompt(
                id=prompt_id,
                content=content,
                moderation_status=moderation_result["status"],
            )
            self.db.add(prompt)
            await self.db.flush()

            # 5. Execute Clustering Assignment
            assignment = await self.clustering_service.assign_to_cluster(
                prompt_id=prompt_id,
                embedding=embedding,
                prompt_content=content,
            )

            # Extract details
            cluster_id = assignment.get("cluster_id")
            similarity_score = assignment.get("similarity_score")
            confidence_score = assignment.get("confidence_score")
            is_new_cluster = assignment.get("is_new_cluster", False)

            latency = time.time() - start_time

            # 6. Structured Telemetry Logging
            log_ai_decision(
                request_id=req_id,
                selected_model=selected_embedding_model,
                routing_reason=f"complexity:{decision.complexity},is_code:{decision.is_code}",
                confidence_score=confidence_score or decision.confidence_estimate,
                similarity_score=similarity_score,
                cluster_id=str(cluster_id) if cluster_id else None,
                latency=latency,
                estimated_token_usage=decision.token_count,
                extra_metadata={
                    "prompt_id": str(prompt_id),
                    "is_new_cluster": is_new_cluster,
                }
            )

            return {
                "status": "accepted",
                "prompt_id": prompt_id,
                "cluster_id": cluster_id,
                "similarity_score": similarity_score,
                "confidence_score": confidence_score,
                "reasoning": assignment.get("reasoning"),
                "is_new_cluster": is_new_cluster,
                "latency_seconds": latency,
            }

        except Exception as e:
            logger.error("Orchestrator: Failed prompt ingestion", request_id=req_id, error=str(e))
            raise

    async def canonicalize_cluster(
        self, cluster_id: uuid.UUID, force_model: Optional[str] = None, trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract a canonical template, calculate dynamic metrics, and write Semantic Lineage history.
        """
        start_time = time.time()
        req_id = trace_id or str(uuid.uuid4())

        try:
            logger.info("Orchestrator: Triggering template extraction & lineage versioning", cluster_id=str(cluster_id))

            # Fetch prompts from cluster
            from src.services.clustering import get_clustering_service
            cluster_prompts = await self.clustering_service.get_cluster_prompts(cluster_id)
            prompts = [p.content for p in cluster_prompts]

            if not prompts:
                raise ValueError(f"No prompts found in cluster {cluster_id}")

            # Run template extraction (which automatically uses routed Portkey clients & retries on confidence checks)
            extraction = await self.canonicalization_service.extract_template(
                cluster_id=cluster_id,
                prompts=prompts,
                force_model=force_model,
                trace_id=req_id,
            )

            # Store and version using PromptLineageEngine
            new_template = await self.lineage_engine.version_template(
                cluster_id=cluster_id,
                new_content=extraction["canonical_template"],
                new_slots=extraction["slots"],
                confidence=extraction["confidence"],
                change_reason=extraction.get("explanation") or "Periodic template extraction",
            )

            latency = time.time() - start_time

            # Log AI decision
            log_ai_decision(
                request_id=req_id,
                selected_model="dynamic-gemini-router",
                routing_reason="canonicalization",
                confidence_score=extraction["confidence"],
                cluster_id=str(cluster_id),
                latency=latency,
                estimated_token_usage=sum(len(p) // 4 for p in prompts),
            )

            return {
                "template_id": new_template.id,
                "canonical_template": new_template.template_content,
                "version": new_template.version,
                "slots": new_template.slots,
                "confidence_score": new_template.confidence_score,
                "latency_seconds": latency,
            }

        except Exception as e:
            logger.error("Orchestrator: Failed template extraction", cluster_id=str(cluster_id), error=str(e))
            raise

    async def detect_drift(
        self,
        cluster_id: uuid.UUID,
        template_id: Optional[uuid.UUID] = None,
        recent_prompts_count: int = 20,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run drift detection on a cluster and log structured telemetry."""
        start_time = time.time()
        req_id = trace_id or str(uuid.uuid4())

        try:
            analysis = await self.drift_service.detect_drift(
                cluster_id=cluster_id,
                template_id=template_id,
                recent_prompts_count=recent_prompts_count,
                trace_id=req_id
            )
            latency = time.time() - start_time

            log_ai_decision(
                request_id=req_id,
                selected_model=self.drift_service.model,
                routing_reason="drift_detection",
                confidence_score=1.0 - analysis.get("drift_score", 0.0),
                cluster_id=str(cluster_id),
                latency=latency,
            )

            return analysis
        except Exception as e:
            logger.error("Orchestrator: Failed drift detection", cluster_id=str(cluster_id), error=str(e))
            raise
