"""Family relationship mapping service for prompt families."""

import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.clients.portkey import AsyncPortkeyClient, PortkeyClientError, get_async_portkey_client
from src.config.settings import get_settings
from src.models.database import (
    Cluster,
    FamilyClusterMapping,
    PromptFamily,
)
from src.services.drift_detection import DriftDetectionService, get_drift_detection_service

logger = get_logger(__name__)


class FamilyTrackingService:
    """Service for tracking prompt family relationships."""

    def __init__(
        self,
        db: AsyncSession,
        client: Optional[AsyncPortkeyClient] = None,
        drift_service: Optional[DriftDetectionService] = None,
    ):
        """
        Initialize family tracking service.

        Args:
            db: Database session
            client: Optional AsyncPortkeyClient instance
            drift_service: Optional DriftDetectionService instance
        """
        self.db = db
        settings = get_settings()
        self.model = settings.models.reasoning.model
        self.max_tokens = settings.models.reasoning.max_tokens

        self.client = client or get_async_portkey_client(provider=self.model)
        self.drift_service = drift_service or get_drift_detection_service(db)

        logger.info("Family tracking service initialized", model=self.model)

    async def create_family(
        self,
        name: str,
        description: Optional[str] = None,
        parent_family_id: Optional[uuid.UUID] = None,
    ) -> PromptFamily:
        """
        Create a new prompt family.

        Args:
            name: Family name
            description: Optional description
            parent_family_id: Optional parent family ID

        Returns:
            Created PromptFamily object
        """
        try:
            family = PromptFamily(
                name=name,
                description=description,
                parent_family_id=parent_family_id,
            )

            self.db.add(family)
            await self.db.flush()

            logger.info(
                "Prompt family created",
                family_id=family.id,
                name=name,
                parent_family_id=parent_family_id,
            )

            return family

        except Exception as e:
            logger.error("Error creating prompt family", name=name, error=str(e))
            raise

    async def map_cluster_to_family(
        self, cluster_id: uuid.UUID, family_id: uuid.UUID
    ) -> FamilyClusterMapping:
        """
        Map a cluster to a family.

        Args:
            cluster_id: Cluster ID
            family_id: Family ID

        Returns:
            Created FamilyClusterMapping object
        """
        try:
            # Check if mapping already exists
            from sqlalchemy import select

            stmt = select(FamilyClusterMapping).where(
                FamilyClusterMapping.cluster_id == cluster_id,
                FamilyClusterMapping.family_id == family_id,
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.debug(
                    "Cluster already mapped to family",
                    cluster_id=cluster_id,
                    family_id=family_id,
                )
                return existing

            mapping = FamilyClusterMapping(
                cluster_id=cluster_id,
                family_id=family_id,
            )

            self.db.add(mapping)
            await self.db.flush()

            logger.info(
                "Cluster mapped to family",
                cluster_id=cluster_id,
                family_id=family_id,
            )

            return mapping

        except Exception as e:
            logger.error(
                "Error mapping cluster to family",
                cluster_id=cluster_id,
                family_id=family_id,
                error=str(e),
            )
            raise

    async def get_family_clusters(self, family_id: uuid.UUID) -> List[Cluster]:
        """
        Get all clusters in a family.

        Args:
            family_id: Family ID

        Returns:
            List of Cluster objects
        """
        from sqlalchemy import select

        stmt = (
            select(Cluster)
            .join(FamilyClusterMapping)
            .where(FamilyClusterMapping.family_id == family_id)
        )

        result = await self.db.execute(stmt)
        clusters = result.scalars().all()

        return clusters

    async def get_family_hierarchy(self, family_id: uuid.UUID) -> Dict[str, Any]:
        """
        Get family hierarchy (parent and children).

        Args:
            family_id: Family ID

        Returns:
            Family hierarchy dictionary
        """
        family = await self.db.get(PromptFamily, family_id)
        if not family:
            return {}

        # Get parent family
        parent = None
        if family.parent_family_id:
            parent = await self.db.get(PromptFamily, family.parent_family_id)

        # Get child families
        from sqlalchemy import select

        stmt = select(PromptFamily).where(PromptFamily.parent_family_id == family_id)
        result = await self.db.execute(stmt)
        children = result.scalars().all()

        # Get clusters
        clusters = await self.get_family_clusters(family_id)

        return {
            "family": {
                "id": str(family.id),
                "name": family.name,
                "description": family.description,
            },
            "parent": {
                "id": str(parent.id),
                "name": parent.name,
            } if parent else None,
            "children": [
                {"id": str(child.id), "name": child.name} for child in children
            ],
            "clusters": [{"id": str(c.id), "name": c.name} for c in clusters],
        }

    def _build_split_merge_prompt(
        self,
        family_clusters: List[Cluster],
        drift_analyses: Dict[uuid.UUID, Dict[str, Any]],
    ) -> str:
        """
        Build prompt for split/merge decision.

        Args:
            family_clusters: Clusters in the family
            drift_analyses: Drift analysis results for clusters

        Returns:
            Split/merge analysis prompt
        """
        clusters_info = []
        for cluster in family_clusters:
            drift = drift_analyses.get(cluster.id, {})
            clusters_info.append(
                {
                    "cluster_id": str(cluster.id),
                    "name": cluster.name,
                    "drift_detected": drift.get("has_drift", False),
                    "drift_score": drift.get("drift_score", 0.0),
                    "drift_reasoning": drift.get("reasoning", ""),
                }
            )

        return f"""You are an expert at analyzing prompt family relationships and determining when families should be split or merged.

Given a prompt family with multiple clusters and their drift analyses, determine if the family should be split or merged.

Family Clusters:
{json.dumps(clusters_info, indent=2)}

Task:
1. Analyze if clusters in this family should remain together or be split
2. Determine if any clusters should be merged with other families
3. Provide reasoning for your decision
4. Recommend action: "keep", "split", or "merge"

Return a JSON object with:
- decision: "keep", "split", or "merge"
- reasoning: detailed explanation
- recommended_actions: array of specific actions to take
- confidence: confidence score (0.0-1.0)

Example output:
{{
  "decision": "split",
  "reasoning": "Cluster A shows significant drift (score: 0.75) and has diverged semantically from the family. It should be split into a new family.",
  "recommended_actions": [
    "Create new family for Cluster A",
    "Keep Cluster B and C in original family"
  ],
  "confidence": 0.85
}}
"""

    async def analyze_family_split_merge(
        self,
        family_id: uuid.UUID,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze if a family should be split or merged using o1-mini.

        Args:
            family_id: Family ID
            trace_id: Optional trace ID

        Returns:
            Split/merge analysis result
        """
        try:
            # Get family clusters
            clusters = await self.get_family_clusters(family_id)

            if len(clusters) < 2:
                return {
                    "decision": "keep",
                    "reasoning": "Family has fewer than 2 clusters, no split/merge needed",
                    "recommended_actions": [],
                    "confidence": 1.0,
                }

            # Get drift analyses for clusters
            drift_analyses = await self.drift_service.detect_drift_batch(
                [c.id for c in clusters], trace_id=trace_id
            )

            # Build analysis prompt
            analysis_prompt = self._build_split_merge_prompt(clusters, drift_analyses)

            # Use with_options for request-level overrides
            client_with_options = (
                self.client.with_options(trace_id=trace_id) if trace_id else self.client
            )

            # Call o1-mini for analysis
            response = await client_with_options.chat_completions_create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing prompt family relationships. Always return valid JSON.",
                    },
                    {"role": "user", "content": analysis_prompt},
                ],
                max_tokens=self.max_tokens,
            )

            # Parse response
            content = response.choices[0].message.content

            # Extract JSON from response
            import re

            json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)

            analysis = json.loads(content)

            logger.info(
                "Family split/merge analysis completed",
                family_id=family_id,
                decision=analysis.get("decision"),
                confidence=analysis.get("confidence"),
                trace_id=trace_id,
            )

            return analysis

        except json.JSONDecodeError as e:
            logger.error("JSON decode error in family analysis", error=str(e), trace_id=trace_id)
            raise PortkeyClientError(f"Invalid JSON response from family analysis: {e}") from e
        except Exception as e:
            logger.error(
                "Error analyzing family split/merge",
                family_id=family_id,
                error=str(e),
                trace_id=trace_id,
            )
            raise

    async def split_family(
        self,
        family_id: uuid.UUID,
        cluster_ids_to_split: List[uuid.UUID],
        new_family_name: Optional[str] = None,
        reasoning: Optional[str] = None,
    ) -> PromptFamily:
        """
        Split clusters from a family into a new family.

        Args:
            family_id: Original family ID
            cluster_ids_to_split: Cluster IDs to move to new family
            new_family_name: Optional name for new family
            reasoning: Optional reasoning for split

        Returns:
            Created new PromptFamily object
        """
        try:
            # Get original family
            original_family = await self.db.get(PromptFamily, family_id)
            if not original_family:
                raise ValueError(f"Family {family_id} not found")

            # Create new family
            new_family_name = new_family_name or f"{original_family.name} (Split)"
            new_family = await self.create_family(
                name=new_family_name,
                description=f"Split from {original_family.name}. {reasoning or ''}",
                parent_family_id=family_id,
            )

            # Move clusters to new family
            for cluster_id in cluster_ids_to_split:
                # Remove from original family
                from sqlalchemy import delete, select

                stmt = delete(FamilyClusterMapping).where(
                    FamilyClusterMapping.cluster_id == cluster_id,
                    FamilyClusterMapping.family_id == family_id,
                )
                await self.db.execute(stmt)

                # Add to new family
                await self.map_cluster_to_family(cluster_id, new_family.id)

            await self.db.commit()

            logger.info(
                "Family split completed",
                original_family_id=family_id,
                new_family_id=new_family.id,
                clusters_moved=len(cluster_ids_to_split),
            )

            return new_family

        except Exception as e:
            logger.error("Error splitting family", family_id=family_id, error=str(e))
            await self.db.rollback()
            raise

    async def merge_families(
        self,
        source_family_id: uuid.UUID,
        target_family_id: uuid.UUID,
        reasoning: Optional[str] = None,
    ) -> None:
        """
        Merge source family into target family.

        Args:
            source_family_id: Source family ID (will be merged)
            target_family_id: Target family ID (will receive clusters)
            reasoning: Optional reasoning for merge
        """
        try:
            # Get source family clusters
            source_clusters = await self.get_family_clusters(source_family_id)

            # Move all clusters to target family
            for cluster in source_clusters:
                # Remove from source family
                from sqlalchemy import delete

                stmt = delete(FamilyClusterMapping).where(
                    FamilyClusterMapping.cluster_id == cluster.id,
                    FamilyClusterMapping.family_id == source_family_id,
                )
                await self.db.execute(stmt)

                # Add to target family
                await self.map_cluster_to_family(cluster.id, target_family_id)

            # Update source family description
            source_family = await self.db.get(PromptFamily, source_family_id)
            if source_family:
                merge_note = f"Merged into {target_family_id}. {reasoning or ''}"
                source_family.description = (
                    f"{source_family.description or ''}\n{merge_note}"
                )

            await self.db.commit()

            logger.info(
                "Families merged",
                source_family_id=source_family_id,
                target_family_id=target_family_id,
                clusters_moved=len(source_clusters),
            )

        except Exception as e:
            logger.error(
                "Error merging families",
                source_family_id=source_family_id,
                target_family_id=target_family_id,
                error=str(e),
            )
            await self.db.rollback()
            raise


def get_family_tracking_service(
    db: AsyncSession,
    client: Optional[AsyncPortkeyClient] = None,
    drift_service: Optional[DriftDetectionService] = None,
) -> FamilyTrackingService:
    """
    Get family tracking service instance.

    Args:
        db: Database session
        client: Optional AsyncPortkeyClient instance
        drift_service: Optional DriftDetectionService instance

    Returns:
        FamilyTrackingService instance
    """
    return FamilyTrackingService(db=db, client=client, drift_service=drift_service)

