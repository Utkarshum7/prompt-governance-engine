"""Drift detection service using o1-mini for semantic shift detection."""

import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.clients.portkey import AsyncPortkeyClient, PortkeyClientError, get_async_portkey_client
from src.config.settings import get_settings
from src.models.database import CanonicalTemplate, Cluster
from src.services.evolution import EvolutionTrackingService, get_evolution_tracking_service

logger = get_logger(__name__)


class DriftDetectionService:
    """Service for detecting semantic drift using o1-mini."""

    def __init__(
        self,
        db: AsyncSession,
        client: Optional[AsyncPortkeyClient] = None,
        evolution_service: Optional[EvolutionTrackingService] = None,
    ):
        """
        Initialize drift detection service.

        Args:
            db: Database session
            client: Optional AsyncPortkeyClient instance
            evolution_service: Optional EvolutionTrackingService instance
        """
        self.db = db
        settings = get_settings()
        self.model = settings.models.reasoning.model
        self.max_tokens = settings.models.reasoning.max_tokens

        self.client = client or get_async_portkey_client(provider=self.model)
        self.evolution_service = evolution_service or get_evolution_tracking_service(db)

        logger.info("Drift detection service initialized", model=self.model)

    def _build_drift_analysis_prompt(
        self, template: CanonicalTemplate, recent_prompts: List[str]
    ) -> str:
        """
        Build prompt for drift analysis.

        Args:
            template: Canonical template
            recent_prompts: Recent prompts from the cluster

        Returns:
            Drift analysis prompt
        """
        recent_prompts_text = "\n\n".join(
            [f"Prompt {i+1}:\n{p}" for i, p in enumerate(recent_prompts)]
        )

        return f"""You are an expert at detecting semantic drift in prompt templates.

Given a canonical template and recent prompts from its cluster, analyze whether semantic drift has occurred.

Canonical Template (Version {template.version}):
{template.template_content}

Template Slots:
{json.dumps(template.slots or [], indent=2)}

Recent Prompts from Cluster:
{recent_prompts_text}

Task:
1. Analyze if the recent prompts still match the canonical template semantically
2. Detect any semantic shifts or drift in meaning, intent, or structure
3. Identify if new patterns have emerged that differ from the template
4. Calculate a drift score (0.0 = no drift, 1.0 = complete drift)
5. Provide reasoning for your analysis

Return a JSON object with:
- has_drift: boolean indicating if drift was detected
- drift_score: float between 0.0 and 1.0
- reasoning: detailed explanation of drift analysis
- detected_changes: array of specific changes detected
- recommendation: recommendation for action (none, update_template, create_new_template)

Example output:
{{
  "has_drift": true,
  "drift_score": 0.65,
  "reasoning": "Recent prompts show a shift from translation requests to summarization requests, indicating semantic drift in the cluster",
  "detected_changes": [
    "Intent changed from translation to summarization",
    "New variable patterns emerged"
  ],
  "recommendation": "update_template"
}}
"""

    async def detect_drift(
        self,
        cluster_id: uuid.UUID,
        template_id: Optional[uuid.UUID] = None,
        recent_prompts_count: int = 20,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Detect semantic drift in a cluster.

        Args:
            cluster_id: Cluster ID
            template_id: Optional template ID. If None, uses latest template.
            recent_prompts_count: Number of recent prompts to analyze
            trace_id: Optional trace ID

        Returns:
            Drift analysis result
        """
        try:
            # Get cluster
            cluster = await self.db.get(Cluster, cluster_id)
            if not cluster:
                raise ValueError(f"Cluster {cluster_id} not found")

            # Get template
            if template_id:
                template = await self.db.get(CanonicalTemplate, template_id)
            else:
                # Get latest template for cluster
                from sqlalchemy import select

                stmt = (
                    select(CanonicalTemplate)
                    .where(CanonicalTemplate.cluster_id == cluster_id)
                    .order_by(CanonicalTemplate.created_at.desc())
                    .limit(1)
                )
                result = await self.db.execute(stmt)
                template = result.scalar_one_or_none()

            if not template:
                raise ValueError(f"No template found for cluster {cluster_id}")

            # Get recent prompts from cluster
            from src.services.clustering import get_clustering_service

            clustering_service = get_clustering_service(self.db)
            cluster_prompts = await clustering_service.get_cluster_prompts(cluster_id)

            # Get most recent prompts
            recent_prompts = [
                p.content
                for p in sorted(
                    cluster_prompts, key=lambda x: x.created_at, reverse=True
                )[:recent_prompts_count]
            ]

            if len(recent_prompts) < 5:
                logger.warning(
                    "Insufficient prompts for drift detection",
                    cluster_id=cluster_id,
                    prompts_count=len(recent_prompts),
                )
                return {
                    "has_drift": False,
                    "drift_score": 0.0,
                    "reasoning": "Insufficient prompts for drift detection",
                    "detected_changes": [],
                    "recommendation": "none",
                }

            # Build analysis prompt
            analysis_prompt = self._build_drift_analysis_prompt(template, recent_prompts)

            # Use with_options for request-level overrides
            client_with_options = (
                self.client.with_options(trace_id=trace_id) if trace_id else self.client
            )

            # Call o1-mini for drift analysis
            response = await client_with_options.chat_completions_create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at detecting semantic drift. Always return valid JSON.",
                    },
                    {"role": "user", "content": analysis_prompt},
                ],
                max_tokens=self.max_tokens,
            )

            # Parse response
            content = response.choices[0].message.content

            # Extract JSON from response (o1-mini may wrap in markdown)
            import re

            json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)

            drift_analysis = json.loads(content)

            logger.info(
                "Drift detection completed",
                cluster_id=cluster_id,
                template_id=template_id,
                has_drift=drift_analysis.get("has_drift", False),
                drift_score=drift_analysis.get("drift_score", 0.0),
                trace_id=trace_id,
            )

            # Record drift detection event if drift detected
            if drift_analysis.get("has_drift", False):
                await self.evolution_service.record_drift_detection(
                    template_id=template.id,
                    drift_analysis=drift_analysis,
                    detected_by=self.model,
                )

            return drift_analysis

        except json.JSONDecodeError as e:
            logger.error("JSON decode error in drift detection", error=str(e), trace_id=trace_id)
            raise PortkeyClientError(f"Invalid JSON response from drift detection: {e}") from e
        except Exception as e:
            logger.error(
                "Error detecting drift",
                cluster_id=cluster_id,
                template_id=template_id,
                error=str(e),
                trace_id=trace_id,
            )
            raise

    async def detect_drift_batch(
        self,
        cluster_ids: List[uuid.UUID],
        recent_prompts_count: int = 20,
        trace_id: Optional[str] = None,
    ) -> Dict[uuid.UUID, Dict[str, Any]]:
        """
        Detect drift for multiple clusters.

        Args:
            cluster_ids: List of cluster IDs
            recent_prompts_count: Number of recent prompts to analyze per cluster
            trace_id: Optional trace ID

        Returns:
            Dictionary mapping cluster_id to drift analysis result
        """
        results = {}

        for cluster_id in cluster_ids:
            try:
                drift_result = await self.detect_drift(
                    cluster_id=cluster_id,
                    recent_prompts_count=recent_prompts_count,
                    trace_id=trace_id,
                )
                results[cluster_id] = drift_result
            except Exception as e:
                logger.error(
                    "Error detecting drift for cluster",
                    cluster_id=cluster_id,
                    error=str(e),
                )
                results[cluster_id] = {
                    "has_drift": False,
                    "drift_score": 0.0,
                    "reasoning": f"Error: {str(e)}",
                    "detected_changes": [],
                    "recommendation": "none",
                }

        return results


def get_drift_detection_service(
    db: AsyncSession,
    client: Optional[AsyncPortkeyClient] = None,
    evolution_service: Optional[EvolutionTrackingService] = None,
) -> DriftDetectionService:
    """
    Get drift detection service instance.

    Args:
        db: Database session
        client: Optional AsyncPortkeyClient instance
        evolution_service: Optional EvolutionTrackingService instance

    Returns:
        DriftDetectionService instance
    """
    return DriftDetectionService(
        db=db, client=client, evolution_service=evolution_service
    )

