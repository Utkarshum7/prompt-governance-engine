"""Prompt Lineage Engine for template versioning and evolution tracking."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.models.database import CanonicalTemplate, EvolutionEvent, PromptFamily, FamilyClusterMapping

logger = get_logger(__name__)


class PromptLineageEngine:
    """Lineage Engine tracks versioning, family hierarchies, and drift events."""

    def __init__(self, db: AsyncSession):
        """Initialize Prompt Lineage Engine."""
        self.db = db

    def increment_semantic_version(
        self, current_version: str, change_type: Literal["major", "minor", "patch"]
    ) -> str:
        """Increment a semantic version string (e.g. 1.0.0)."""
        try:
            parts = [int(p) for p in current_version.split(".")]
            if len(parts) != 3:
                parts = [1, 0, 0]
        except Exception:
            parts = [1, 0, 0]

        if change_type == "major":
            parts[0] += 1
            parts[1] = 0
            parts[2] = 0
        elif change_type == "minor":
            parts[1] += 1
            parts[2] = 0
        else:
            parts[2] += 1

        return f"{parts[0]}.{parts[1]}.{parts[2]}"

    async def version_template(
        self,
        cluster_id: uuid.UUID,
        new_content: str,
        new_slots: List[Dict[str, Any]],
        confidence: float,
        change_reason: str,
    ) -> CanonicalTemplate:
        """
        Version a template by checking the previous template, incrementing the version,
        and logging an evolution event.
        """
        # Fetch the latest template for the cluster
        stmt = (
            select(CanonicalTemplate)
            .where(CanonicalTemplate.cluster_id == cluster_id)
            .order_by(CanonicalTemplate.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        old_template = result.scalar_one_or_none()

        if old_template is None:
            # First version
            new_version = "1.0.0"
            previous_version = None
            event_type = "CREATED"
        else:
            previous_version = old_template.version
            # Analyze slot changes to determine semantic change type
            old_slots = old_template.slots or []
            old_slot_names = {s.get("name") for s in old_slots if s.get("name")}
            new_slot_names = {s.get("name") for s in new_slots if s.get("name")}

            if old_slot_names != new_slot_names:
                change_type = "major"  # Structural slot change
            elif old_template.template_content != new_content:
                change_type = "minor"  # Content wording change
            else:
                change_type = "patch"  # Metadata only change

            new_version = self.increment_semantic_version(previous_version, change_type)
            event_type = "UPDATED"

        # Create new template
        template_id = uuid.uuid4()
        new_template = CanonicalTemplate(
            id=template_id,
            cluster_id=cluster_id,
            template_content=new_content,
            version=new_version,
            slots=new_slots,
            confidence_score=confidence,
        )
        self.db.add(new_template)
        await self.db.flush()

        # Create evolution event
        event = EvolutionEvent(
            id=uuid.uuid4(),
            template_id=template_id,
            event_type=event_type,
            previous_version=previous_version,
            new_version=new_version,
            change_reason=change_reason,
            detected_by="PromptLineageEngine",
        )
        self.db.add(event)
        await self.db.flush()

        logger.info(
            "Template versioned successfully",
            cluster_id=str(cluster_id),
            version=new_version,
            event=event_type,
        )

        return new_template

    async def create_family_hierarchy(
        self, name: str, parent_id: Optional[uuid.UUID] = None, description: Optional[str] = None
    ) -> PromptFamily:
        """Create a prompt family and attach a parent-child lineage link."""
        family = PromptFamily(
            id=uuid.uuid4(),
            parent_family_id=parent_id,
            name=name,
            description=description,
        )
        self.db.add(family)
        await self.db.flush()
        logger.info("Lineage family hierarchy link created", family_id=str(family.id), parent_id=str(parent_id))
        return family

    async def get_template_history(self, cluster_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Retrieve full template evolution history and drift events for a cluster."""
        stmt = (
            select(CanonicalTemplate)
            .where(CanonicalTemplate.cluster_id == cluster_id)
            .order_by(CanonicalTemplate.version.asc())
        )
        result = await self.db.execute(stmt)
        templates = result.scalars().all()

        history = []
        for t in templates:
            # Fetch evolution events
            event_stmt = select(EvolutionEvent).where(EvolutionEvent.template_id == t.id)
            event_res = await self.db.execute(event_stmt)
            events = event_res.scalars().all()

            history.append({
                "template_id": str(t.id),
                "version": t.version,
                "content": t.template_content,
                "slots": t.slots,
                "confidence_score": t.confidence_score,
                "created_at": t.created_at.isoformat(),
                "events": [
                    {
                        "event_type": e.event_type,
                        "previous_version": e.previous_version,
                        "new_version": e.new_version,
                        "change_reason": e.change_reason,
                        "detected_by": e.detected_by,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in events
                ]
            })

        return history
