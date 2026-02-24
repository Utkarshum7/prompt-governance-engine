"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Prompt Schemas
class PromptCreateRequest(BaseModel):
    """Request schema for creating a prompt."""

    content: str = Field(..., description="Prompt content", min_length=1, max_length=10000)


class PromptResponse(BaseModel):
    """Response schema for a prompt."""

    id: UUID
    content: str
    moderation_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptIngestionResponse(BaseModel):
    """Response schema for prompt ingestion."""

    prompt_id: UUID
    cluster_id: Optional[UUID] = None
    similarity_score: Optional[float] = None
    confidence_score: Optional[float] = None
    reasoning: Optional[str] = None
    status: str
    is_new_cluster: bool = False


# Cluster Schemas
class ClusterResponse(BaseModel):
    """Response schema for a cluster."""

    id: UUID
    name: Optional[str] = None
    similarity_threshold: Optional[float] = None
    confidence_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    prompt_count: Optional[int] = None

    class Config:
        from_attributes = True


class ClusterDetailResponse(ClusterResponse):
    """Detailed cluster response with prompts."""

    prompts: List[PromptResponse] = []


class ClusterListResponse(BaseModel):
    """Response schema for cluster list."""

    clusters: List[ClusterResponse]
    total: int
    page: int = 1
    page_size: int = 20


# Template Schemas
class TemplateSlotResponse(BaseModel):
    """Response schema for a template slot."""

    name: str
    type: Optional[str] = None
    example_values: Optional[List[str]] = None
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


class TemplateResponse(BaseModel):
    """Response schema for a template."""

    id: UUID
    cluster_id: UUID
    template_content: str
    version: str
    slots: Optional[List[Dict[str, Any]]] = None
    confidence_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateDetailResponse(TemplateResponse):
    """Detailed template response with slots."""

    template_slots: List[TemplateSlotResponse] = []


class TemplateListResponse(BaseModel):
    """Response schema for template list."""

    templates: List[TemplateResponse]
    total: int
    page: int = 1
    page_size: int = 20


# Evolution Schemas
class EvolutionEventResponse(BaseModel):
    """Response schema for an evolution event."""

    id: UUID
    template_id: UUID
    event_type: str
    previous_version: Optional[str] = None
    new_version: Optional[str] = None
    change_reason: Optional[str] = None
    detected_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EvolutionEventListResponse(BaseModel):
    """Response schema for evolution event list."""

    events: List[EvolutionEventResponse]
    total: int
    page: int = 1
    page_size: int = 20


# Family Schemas
class PromptFamilyResponse(BaseModel):
    """Response schema for a prompt family."""

    id: UUID
    name: str
    description: Optional[str] = None
    parent_family_id: Optional[UUID] = None
    created_at: datetime
    cluster_count: Optional[int] = None

    class Config:
        from_attributes = True


class PromptFamilyListResponse(BaseModel):
    """Response schema for prompt family list."""

    families: List[PromptFamilyResponse]
    total: int


# Drift Detection Schemas
class DriftDetectionResponse(BaseModel):
    """Response schema for drift detection."""

    cluster_id: UUID
    template_id: Optional[UUID] = None
    has_drift: bool
    drift_score: float
    reasoning: str
    detected_changes: List[str] = []
    recommendation: str


# Error Schemas
class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

