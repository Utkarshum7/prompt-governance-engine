"""Template versioning system for canonical templates."""

import re
import uuid
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.models.database import CanonicalTemplate, EvolutionEvent

logger = get_logger(__name__)


class TemplateVersioningService:
    """Service for versioning canonical templates."""

    def __init__(self, db: AsyncSession):
        """
        Initialize template versioning service.

        Args:
            db: Database session
        """
        self.db = db
        logger.info("Template versioning service initialized")

    def _parse_version(self, version: str) -> Dict[str, int]:
        """
        Parse semantic version string.

        Args:
            version: Version string (e.g., "1.2.3")

        Returns:
            Dictionary with major, minor, patch
        """
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
        if not match:
            raise ValueError(f"Invalid version format: {version}")

        return {
            "major": int(match.group(1)),
            "minor": int(match.group(2)),
            "patch": int(match.group(3)),
        }

    def _increment_version(
        self, current_version: str, version_type: str = "patch"
    ) -> str:
        """
        Increment version number.

        Args:
            current_version: Current version string
            version_type: Type of increment ("major", "minor", "patch")

        Returns:
            New version string
        """
        version_parts = self._parse_version(current_version)

        if version_type == "major":
            version_parts["major"] += 1
            version_parts["minor"] = 0
            version_parts["patch"] = 0
        elif version_type == "minor":
            version_parts["minor"] += 1
            version_parts["patch"] = 0
        else:  # patch
            version_parts["patch"] += 1

        return f"{version_parts['major']}.{version_parts['minor']}.{version_parts['patch']}"

    def _detect_version_change_type(
        self, old_template: str, new_template: str, old_slots: List[Dict], new_slots: List[Dict]
    ) -> str:
        """
        Detect type of version change.

        Args:
            old_template: Old template content
            new_template: New template content
            old_slots: Old slot definitions
            new_slots: New slot definitions

        Returns:
            Version change type ("major", "minor", "patch")
        """
        old_slot_names = {s.get("name") for s in old_slots}
        new_slot_names = {s.get("name") for s in new_slots}

        # Major: Template structure changed significantly
        if old_template != new_template and len(old_slot_names.symmetric_difference(new_slot_names)) > 0:
            return "major"

        # Minor: Slots added or removed
        if old_slot_names != new_slot_names:
            return "minor"

        # Patch: Slot types or examples changed, but same slots
        return "patch"

    async def create_version(
        self,
        cluster_id: uuid.UUID,
        template_content: str,
        slots: List[Dict],
        previous_template_id: Optional[uuid.UUID] = None,
        change_reason: Optional[str] = None,
        detected_by: Optional[str] = None,
    ) -> CanonicalTemplate:
        """
        Create a new template version.

        Args:
            cluster_id: Cluster ID
            template_content: Template content
            slots: Slot definitions
            previous_template_id: Optional previous template ID
            change_reason: Reason for version change
            detected_by: Model or system that detected the change

        Returns:
            Created CanonicalTemplate object
        """
        try:
            # Determine version
            if previous_template_id:
                # Get previous template
                previous_template = await self.db.get(CanonicalTemplate, previous_template_id)
                if previous_template:
                    # Detect change type
                    old_slots = previous_template.slots or []
                    change_type = self._detect_version_change_type(
                        previous_template.template_content,
                        template_content,
                        old_slots,
                        slots,
                    )
                    new_version = self._increment_version(previous_template.version, change_type)

                    # Create evolution event
                    evolution_event = EvolutionEvent(
                        template_id=previous_template_id,
                        event_type="UPDATED",
                        previous_version=previous_template.version,
                        new_version=new_version,
                        change_reason=change_reason or f"Template updated ({change_type} change)",
                        detected_by=detected_by or "system",
                    )
                    self.db.add(evolution_event)
                else:
                    new_version = "1.0.0"
            else:
                # First version
                new_version = "1.0.0"

                # Create evolution event
                template_id = uuid.uuid4()
                evolution_event = EvolutionEvent(
                    template_id=template_id,
                    event_type="CREATED",
                    previous_version=None,
                    new_version=new_version,
                    change_reason=change_reason or "Initial template creation",
                    detected_by=detected_by or "system",
                )
                self.db.add(evolution_event)

            # Create new template version
            template_id = uuid.uuid4()
            canonical_template = CanonicalTemplate(
                id=template_id,
                cluster_id=cluster_id,
                template_content=template_content,
                version=new_version,
                slots=slots,
            )

            self.db.add(canonical_template)
            await self.db.flush()

            logger.info(
                "Template version created",
                template_id=template_id,
                cluster_id=cluster_id,
                version=new_version,
                previous_template_id=previous_template_id,
            )

            return canonical_template

        except Exception as e:
            logger.error("Error creating template version", error=str(e))
            raise

    async def get_template_versions(self, cluster_id: uuid.UUID) -> List[CanonicalTemplate]:
        """
        Get all template versions for a cluster.

        Args:
            cluster_id: Cluster ID

        Returns:
            List of CanonicalTemplate objects sorted by version
        """
        from sqlalchemy import select

        stmt = select(CanonicalTemplate).where(
            CanonicalTemplate.cluster_id == cluster_id
        ).order_by(CanonicalTemplate.created_at)

        result = await self.db.execute(stmt)
        templates = result.scalars().all()

        # Sort by version (semantic versioning)
        def version_key(template: CanonicalTemplate) -> tuple:
            try:
                parts = self._parse_version(template.version)
                return (parts["major"], parts["minor"], parts["patch"])
            except ValueError:
                return (0, 0, 0)

        templates.sort(key=version_key)

        return templates

    async def get_latest_version(self, cluster_id: uuid.UUID) -> Optional[CanonicalTemplate]:
        """
        Get latest template version for a cluster.

        Args:
            cluster_id: Cluster ID

        Returns:
            Latest CanonicalTemplate or None
        """
        versions = await self.get_template_versions(cluster_id)
        return versions[-1] if versions else None

    async def get_evolution_history(
        self, template_id: uuid.UUID
    ) -> List[EvolutionEvent]:
        """
        Get evolution history for a template.

        Args:
            template_id: Template ID

        Returns:
            List of EvolutionEvent objects
        """
        from sqlalchemy import select

        stmt = select(EvolutionEvent).where(
            EvolutionEvent.template_id == template_id
        ).order_by(EvolutionEvent.created_at)

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        return events


def get_template_versioning_service(db: AsyncSession) -> TemplateVersioningService:
    """
    Get template versioning service instance.

    Args:
        db: Database session

    Returns:
        TemplateVersioningService instance
    """
    return TemplateVersioningService(db)

