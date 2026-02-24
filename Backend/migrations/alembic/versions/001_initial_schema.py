"""Initial database schema

Revision ID: 001_initial
Revises: 
Create Date: 2025-01-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Create prompts table
    op.create_table(
        "prompts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("moderation_status", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create clusters table
    op.create_table(
        "clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("centroid_embedding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("similarity_threshold", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create cluster_assignments table
    op.create_table(
        "cluster_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prompt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"], ondelete="CASCADE"),
    )

    # Create canonical_templates table
    op.create_table(
        "canonical_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_content", sa.Text(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("slots", postgresql.JSONB(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"], ondelete="CASCADE"),
    )

    # Create template_slots table
    op.create_table(
        "template_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_name", sa.String(255), nullable=False),
        sa.Column("slot_type", sa.String(100), nullable=True),
        sa.Column("example_values", postgresql.JSONB(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["canonical_templates.id"], ondelete="CASCADE"),
    )

    # Create evolution_events table
    op.create_table(
        "evolution_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("previous_version", sa.String(50), nullable=True),
        sa.Column("new_version", sa.String(50), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("detected_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["canonical_templates.id"], ondelete="CASCADE"),
    )

    # Create prompt_families table
    op.create_table(
        "prompt_families",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_family_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_family_id"], ["prompt_families.id"], ondelete="SET NULL"),
    )

    # Create family_cluster_mappings table
    op.create_table(
        "family_cluster_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["prompt_families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"], ondelete="CASCADE"),
    )

    # Create indexes
    op.create_index("ix_prompts_created_at", "prompts", ["created_at"])
    op.create_index("ix_cluster_assignments_prompt_id", "cluster_assignments", ["prompt_id"])
    op.create_index("ix_cluster_assignments_cluster_id", "cluster_assignments", ["cluster_id"])
    op.create_index("ix_canonical_templates_cluster_id", "canonical_templates", ["cluster_id"])
    op.create_index("ix_canonical_templates_version", "canonical_templates", ["version"])
    op.create_index("ix_evolution_events_template_id", "evolution_events", ["template_id"])
    op.create_index("ix_evolution_events_created_at", "evolution_events", ["created_at"])
    
    # Create GIN indexes for JSONB columns
    op.create_index("ix_canonical_templates_slots", "canonical_templates", ["slots"], postgresql_using="gin")
    op.create_index("ix_template_slots_example_values", "template_slots", ["example_values"], postgresql_using="gin")


def downgrade() -> None:
    """Drop initial database schema."""
    # Drop indexes
    op.drop_index("ix_template_slots_example_values", table_name="template_slots")
    op.drop_index("ix_canonical_templates_slots", table_name="canonical_templates")
    op.drop_index("ix_evolution_events_created_at", table_name="evolution_events")
    op.drop_index("ix_evolution_events_template_id", table_name="evolution_events")
    op.drop_index("ix_canonical_templates_version", table_name="canonical_templates")
    op.drop_index("ix_canonical_templates_cluster_id", table_name="canonical_templates")
    op.drop_index("ix_cluster_assignments_cluster_id", table_name="cluster_assignments")
    op.drop_index("ix_cluster_assignments_prompt_id", table_name="cluster_assignments")
    op.drop_index("ix_prompts_created_at", table_name="prompts")

    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table("family_cluster_mappings")
    op.drop_table("prompt_families")
    op.drop_table("evolution_events")
    op.drop_table("template_slots")
    op.drop_table("canonical_templates")
    op.drop_table("cluster_assignments")
    op.drop_table("clusters")
    op.drop_table("prompts")

