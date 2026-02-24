"""SQLAlchemy async models for database tables."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models."""

    pass


class Prompt(Base):
    """Prompt model - stores raw prompt data."""

    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    moderation_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False
    )

    # Relationships
    cluster_assignments: Mapped[List["ClusterAssignment"]] = relationship(
        "ClusterAssignment", back_populates="prompt", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Prompt(id={self.id}, content={self.content[:50]}...)>"


class Cluster(Base):
    """Cluster model - stores prompt clusters."""

    __tablename__ = "clusters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    centroid_embedding_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    similarity_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False
    )

    # Relationships
    cluster_assignments: Mapped[List["ClusterAssignment"]] = relationship(
        "ClusterAssignment", back_populates="cluster", cascade="all, delete-orphan"
    )
    canonical_templates: Mapped[List["CanonicalTemplate"]] = relationship(
        "CanonicalTemplate", back_populates="cluster", cascade="all, delete-orphan"
    )
    family_mappings: Mapped[List["FamilyClusterMapping"]] = relationship(
        "FamilyClusterMapping", back_populates="cluster", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Cluster(id={self.id}, name={self.name})>"


class ClusterAssignment(Base):
    """Cluster assignment model - maps prompts to clusters."""

    __tablename__ = "cluster_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # Relationships
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="cluster_assignments")
    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="cluster_assignments")

    def __repr__(self) -> str:
        return (
            f"<ClusterAssignment(id={self.id}, prompt_id={self.prompt_id}, "
            f"cluster_id={self.cluster_id}, similarity={self.similarity_score})>"
        )


class CanonicalTemplate(Base):
    """Canonical template model - stores extracted templates."""

    __tablename__ = "canonical_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    template_content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    slots: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False
    )

    # Relationships
    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="canonical_templates")
    template_slots: Mapped[List["TemplateSlot"]] = relationship(
        "TemplateSlot", back_populates="template", cascade="all, delete-orphan"
    )
    evolution_events: Mapped[List["EvolutionEvent"]] = relationship(
        "EvolutionEvent", back_populates="template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<CanonicalTemplate(id={self.id}, cluster_id={self.cluster_id}, "
            f"version={self.version})>"
        )


class TemplateSlot(Base):
    """Template slot model - stores variable slots in templates."""

    __tablename__ = "template_slots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    slot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slot_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    example_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # Relationships
    template: Mapped["CanonicalTemplate"] = relationship(
        "CanonicalTemplate", back_populates="template_slots"
    )

    def __repr__(self) -> str:
        return (
            f"<TemplateSlot(id={self.id}, template_id={self.template_id}, "
            f"slot_name={self.slot_name})>"
        )


class EvolutionEvent(Base):
    """Evolution event model - tracks template evolution."""

    __tablename__ = "evolution_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CREATED, UPDATED, etc.
    previous_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detected_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # MODEL_NAME
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # Relationships
    template: Mapped["CanonicalTemplate"] = relationship(
        "CanonicalTemplate", back_populates="evolution_events"
    )

    def __repr__(self) -> str:
        return (
            f"<EvolutionEvent(id={self.id}, template_id={self.template_id}, "
            f"event_type={self.event_type})>"
        )


class PromptFamily(Base):
    """Prompt family model - stores prompt family relationships."""

    __tablename__ = "prompt_families"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_family_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_families.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # Relationships
    parent_family: Mapped[Optional["PromptFamily"]] = relationship(
        "PromptFamily", remote_side=[id], back_populates="child_families"
    )
    child_families: Mapped[List["PromptFamily"]] = relationship(
        "PromptFamily", back_populates="parent_family"
    )
    cluster_mappings: Mapped[List["FamilyClusterMapping"]] = relationship(
        "FamilyClusterMapping", back_populates="family", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PromptFamily(id={self.id}, name={self.name})>"


class FamilyClusterMapping(Base):
    """Family cluster mapping model - maps families to clusters."""

    __tablename__ = "family_cluster_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_families.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # Relationships
    family: Mapped["PromptFamily"] = relationship("PromptFamily", back_populates="cluster_mappings")
    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="family_mappings")

    def __repr__(self) -> str:
        return (
            f"<FamilyClusterMapping(id={self.id}, family_id={self.family_id}, "
            f"cluster_id={self.cluster_id})>"
        )

