"""Evolution tracking service for template changes."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.models.database import EvolutionEvent, CanonicalTemplate

logger = get_logger(__name__)

# Evolution event types
EVENT_TYPES = {
    "CREATED": "Template created",
    "UPDATED": "Template updated",
    "SLOT_ADDED": "Variable slot added",
    "SLOT_REMOVED": "Variable slot removed",
    "SLOT_MODIFIED": "Variable slot modified",
    "DRIFT_DETECTED": "Semantic drift detected",
    "VERSION_INCREMENTED": "Version incremented",
}


class EvolutionTrackingService:
    """Service for tracking template evolution events."""

    def __init__(self, db: AsyncSession):
        """
        Initialize evolution tracking service.

        Args:
            db: Database session
        """
        self.db = db
        logger.info("Evolution tracking service initialized")

    async def record_event(
        self,
        template_id: uuid.UUID,
        event_type: str,
        previous_version: Optional[str] = None,
        new_version: Optional[str] = None,
        change_reason: Optional[str] = None,
        detected_by: Optional[str] = None,
    ) -> EvolutionEvent:
        """
        Record an evolution event.

        Args:
            template_id: Template ID
            event_type: Type of event (CREATED, UPDATED, etc.)
            previous_version: Previous template version
            new_version: New template version
            change_reason: Reason for the change
            detected_by: Model or system that detected the change

        Returns:
            Created EvolutionEvent object
        """
        try:
            # Validate event type
            if event_type not in EVENT_TYPES:
                logger.warning(
                    "Unknown event type, using UPDATED",
                    event_type=event_type,
                    template_id=template_id,
                )
                event_type = "UPDATED"

            event = EvolutionEvent(
                template_id=template_id,
                event_type=event_type,
                previous_version=previous_version,
                new_version=new_version,
                change_reason=change_reason or EVENT_TYPES.get(event_type, "Change detected"),
                detected_by=detected_by or "system",
            )

            self.db.add(event)
            await self.db.flush()

            logger.info(
                "Evolution event recorded",
                event_id=event.id,
                template_id=template_id,
                event_type=event_type,
                previous_version=previous_version,
                new_version=new_version,
            )

            return event

        except Exception as e:
            logger.error(
                "Error recording evolution event",
                template_id=template_id,
                event_type=event_type,
                error=str(e),
            )
            raise

    async def record_slot_change(
        self,
        template_id: uuid.UUID,
        slot_name: str,
        change_type: str,
        previous_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        detected_by: Optional[str] = None,
    ) -> EvolutionEvent:
        """
        Record a slot change event.

        Args:
            template_id: Template ID
            slot_name: Name of the slot
            change_type: Type of change ("SLOT_ADDED", "SLOT_REMOVED", "SLOT_MODIFIED")
            previous_value: Previous slot value
            new_value: New slot value
            detected_by: Model or system that detected the change

        Returns:
            Created EvolutionEvent object
        """
        # Get template to get current version
        template = await self.db.get(CanonicalTemplate, template_id)
        current_version = template.version if template else None

        change_reason = f"Slot '{slot_name}' {change_type.lower().replace('_', ' ')}"
        if previous_value and new_value:
            change_reason += f": {previous_value} -> {new_value}"
        elif previous_value:
            change_reason += f": removed {previous_value}"
        elif new_value:
            change_reason += f": added {new_value}"

        return await self.record_event(
            template_id=template_id,
            event_type=change_type,
            previous_version=current_version,
            new_version=current_version,
            change_reason=change_reason,
            detected_by=detected_by,
        )

    async def record_drift_detection(
        self,
        template_id: uuid.UUID,
        drift_analysis: Dict[str, Any],
        detected_by: Optional[str] = None,
    ) -> EvolutionEvent:
        """
        Record a drift detection event.

        Args:
            template_id: Template ID
            drift_analysis: Drift analysis result
            detected_by: Model that detected the drift

        Returns:
            Created EvolutionEvent object
        """
        template = await self.db.get(CanonicalTemplate, template_id)
        current_version = template.version if template else None

        change_reason = drift_analysis.get("reasoning", "Semantic drift detected")
        if drift_analysis.get("drift_score"):
            change_reason += f" (drift score: {drift_analysis['drift_score']:.3f})"

        return await self.record_event(
            template_id=template_id,
            event_type="DRIFT_DETECTED",
            previous_version=current_version,
            new_version=current_version,
            change_reason=change_reason,
            detected_by=detected_by or "o1-mini",
        )

    async def get_template_evolution(
        self, template_id: uuid.UUID
    ) -> List[EvolutionEvent]:
        """
        Get evolution history for a template.

        Args:
            template_id: Template ID

        Returns:
            List of EvolutionEvent objects ordered by creation time
        """
        from sqlalchemy import select

        stmt = select(EvolutionEvent).where(
            EvolutionEvent.template_id == template_id
        ).order_by(EvolutionEvent.created_at)

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        logger.debug(
            "Retrieved template evolution",
            template_id=template_id,
            events_count=len(events),
        )

        return events

    async def get_recent_events(
        self, limit: int = 100, event_type: Optional[str] = None
    ) -> List[EvolutionEvent]:
        """
        Get recent evolution events.

        Args:
            limit: Maximum number of events to return
            event_type: Optional filter by event type

        Returns:
            List of recent EvolutionEvent objects
        """
        from sqlalchemy import select

        stmt = select(EvolutionEvent).order_by(EvolutionEvent.created_at.desc()).limit(limit)

        if event_type:
            stmt = stmt.where(EvolutionEvent.event_type == event_type)

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        logger.debug(
            "Retrieved recent evolution events",
            limit=limit,
            event_type=event_type,
            events_count=len(events),
        )

        return events


def get_evolution_tracking_service(db: AsyncSession) -> EvolutionTrackingService:
    """
    Get evolution tracking service instance.

    Args:
        db: Database session

    Returns:
        EvolutionTrackingService instance
    """
    return EvolutionTrackingService(db)

