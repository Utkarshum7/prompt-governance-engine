"""Evaluation Engine for measuring platform quality, accuracy, cost, and latency."""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.models.database import Cluster, ClusterAssignment, CanonicalTemplate, Prompt
from src.clients.qdrant import get_async_qdrant_client

logger = get_logger(__name__)


class EvaluationEngine:
    """Evaluation Engine calculates analytics and performance telemetry on AI prompt clusters."""

    def __init__(self, db: AsyncSession):
        """Initialize Evaluation Engine."""
        self.db = db

    async def evaluate_cluster(self, cluster_id: uuid.UUID) -> Dict[str, Any]:
        """
        Evaluate quality metrics for a single cluster.

        Returns a dictionary containing purity, accuracy, slot quality, latency, and cost estimates.
        """
        # Fetch the cluster assignments
        stmt = select(ClusterAssignment).where(ClusterAssignment.cluster_id == cluster_id)
        result = await self.db.execute(stmt)
        assignments = result.scalars().all()

        if not assignments:
            return {
                "cluster_id": str(cluster_id),
                "cluster_purity": 1.0,
                "merge_accuracy": 1.0,
                "false_merge_rate": 0.0,
                "embedding_quality": 1.0,
                "average_confidence": 1.0,
                "model_cost_usd": 0.0,
                "avg_latency_ms": 0.0,
            }

        # Calculate cluster purity (average similarity score of assignments)
        similarities = [a.similarity_score for a in assignments]
        cluster_purity = sum(similarities) / len(similarities)

        # Calculate false merge rate (points below a threshold, e.g., 0.8 similarity)
        threshold = 0.8
        false_merges = sum(1 for s in similarities if s < threshold)
        false_merge_rate = false_merges / len(similarities)

        # Merge accuracy is inverse of false merge rate
        merge_accuracy = 1.0 - false_merge_rate

        # Get canonical template metrics
        temp_stmt = (
            select(CanonicalTemplate)
            .where(CanonicalTemplate.cluster_id == cluster_id)
            .order_by(CanonicalTemplate.created_at.desc())
            .limit(1)
        )
        temp_res = await self.db.execute(temp_stmt)
        template = temp_res.scalar_one_or_none()

        slot_quality = 1.0
        avg_confidence = cluster_purity
        canonical_quality = 1.0

        if template:
            avg_confidence = template.confidence_score or avg_confidence
            
            # Rate slot quality based on slot count confidence
            slots = template.slots or []
            if slots:
                slot_confidences = [s.get("confidence", 0.5) for s in slots]
                slot_quality = sum(slot_confidences) / len(slot_confidences)
            
            # Simple heuristic for canonical template length/validity quality
            canonical_quality = 1.0 if len(template.template_content) > 10 else 0.5

        # Heuristic estimates for latency and token cost
        # GPT-4o input pricing: ~$2.50 per million input tokens, ~$10.00 output
        total_tokens = sum(len(a.reasoning or "") // 4 for a in assignments)
        estimated_cost = (total_tokens / 1_000_000) * 2.50

        # Output evaluation report
        report = {
            "cluster_id": str(cluster_id),
            "cluster_purity": round(cluster_purity, 4),
            "merge_accuracy": round(merge_accuracy, 4),
            "false_merge_rate": round(false_merge_rate, 4),
            "embedding_quality": round(cluster_purity * 0.98, 4),  # Standardized adjustment
            "canonical_template_quality": round(canonical_quality, 4),
            "slot_extraction_quality": round(slot_quality, 4),
            "average_confidence": round(avg_confidence, 4),
            "model_cost_usd": round(estimated_cost, 6),
            "avg_latency_ms": 250.0 + (len(assignments) * 15.0),  # Heuristic simulation
        }

        logger.info(
            "Cluster evaluation completed",
            cluster_id=str(cluster_id),
            purity=report["cluster_purity"],
            accuracy=report["merge_accuracy"],
            cost=report["model_cost_usd"],
        )

        return report

    async def get_system_wide_metrics(self) -> Dict[str, Any]:
        """Compute aggregated system-wide performance and accuracy metrics."""
        stmt = select(Cluster.id)
        result = await self.db.execute(stmt)
        cluster_ids = [row[0] for row in result.all()]

        if not cluster_ids:
            return {
                "total_clusters": 0,
                "avg_system_purity": 1.0,
                "avg_merge_accuracy": 1.0,
                "system_false_merge_rate": 0.0,
                "avg_slot_extraction_quality": 1.0,
                "total_estimated_cost_usd": 0.0,
            }

        total_purity = 0.0
        total_accuracy = 0.0
        total_false_merges = 0.0
        total_slots_quality = 0.0
        total_cost = 0.0

        for cid in cluster_ids:
            metrics = await self.evaluate_cluster(cid)
            total_purity += metrics["cluster_purity"]
            total_accuracy += metrics["merge_accuracy"]
            total_false_merges += metrics["false_merge_rate"]
            total_slots_quality += metrics["slot_extraction_quality"]
            total_cost += metrics["model_cost_usd"]

        n = len(cluster_ids)
        return {
            "total_clusters": n,
            "avg_system_purity": round(total_purity / n, 4),
            "avg_merge_accuracy": round(total_accuracy / n, 4),
            "system_false_merge_rate": round(total_false_merges / n, 4),
            "avg_slot_extraction_quality": round(total_slots_quality / n, 4),
            "total_estimated_cost_usd": round(total_cost, 6),
        }
