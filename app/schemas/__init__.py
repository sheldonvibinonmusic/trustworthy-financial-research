"""Shared Pydantic schemas for the financial research system.

This module provides contract-level data models across the backend,
ingestion, retrieval, validation, and frontend integration layers.
"""

from app.schemas.claims import (
    Claim,
    ClaimStatus,
    EvidenceItem,
    JudgeReview,
    JudgeRole,
    JudgeVerdict,
)
from app.schemas.documents import (
    DocumentRecord,
    DocumentStatus,
    DocumentUploadResponse,
)
from app.schemas.facts import (
    FinancialCalculation,
    FinancialFact,
)
from app.schemas.requests import (
    InputMode,
    RequestedAnalysis,
    ResearchRequest,
    RunCreationResponse,
)
from app.schemas.results import (
    ReportSection,
    ResearchResult,
    RunState,
    RunStatus,
    RunStatusState,
)

__all__ = [
    # Core requested schemas
    "ResearchRequest",
    "DocumentRecord",
    "EvidenceItem",
    "FinancialFact",
    "Claim",
    "JudgeReview",
    "RunStatus",
    "ResearchResult",
    # Enums and supporting schemas
    "ClaimStatus",
    "DocumentStatus",
    "DocumentUploadResponse",
    "FinancialCalculation",
    "InputMode",
    "JudgeRole",
    "JudgeVerdict",
    "ReportSection",
    "RequestedAnalysis",
    "RunCreationResponse",
    "RunState",
    "RunStatusState",
]
