"""Run status and research result schemas."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.schemas.claims import Claim, EvidenceItem, JudgeReview


class RunStatusState(str, Enum):
    """Allowed lifecycle states for a research run."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


# Backward-compatible alias
RunState = RunStatusState


class RunStatus(BaseModel):
    """Execution status for a research run as returned by GET /api/runs/{run_id}."""
    run_id: str = Field(..., min_length=1, description="Unique research run identifier")
    status: RunStatusState = Field(
        default=RunStatusState.QUEUED,
        description="Current lifecycle status of the run"
    )
    current_stage: Optional[str] = Field(
        default=None,
        description="Current active workflow step (e.g. discovery, parsing, retrieval, judge_audit, report_assembly)"
    )
    progress: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Estimated completion fraction (0.0 to 1.0)"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings recorded during execution"
    )
    error: Optional[str] = Field(
        default=None,
        description="Failure details if run status is 'failed'"
    )

    @field_validator("run_id")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only.")
        return stripped


class ReportSection(BaseModel):
    """Individual section within the generated financial research report."""
    section_id: str = Field(..., min_length=1, description="Identifier for this report section")
    title: str = Field(..., min_length=1, description="Section heading")
    content: str = Field(..., description="Markdown or text content of the section")
    claim_ids: List[str] = Field(default_factory=list, description="IDs of claims cited in this section")
    warnings: List[str] = Field(default_factory=list, description="Section-specific warnings")


class ResearchResult(BaseModel):
    """Final comprehensive research report returned by GET /api/runs/{run_id}/result."""
    run_id: str = Field(..., min_length=1, description="Unique research run identifier")
    status: RunStatusState = Field(
        default=RunStatusState.COMPLETED,
        description="Final lifecycle status of the run"
    )
    company: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata on the target company (e.g. name, ticker, jurisdiction)"
    )
    periods: Dict[str, Any] = Field(
        default_factory=dict,
        description="Financial periods analyzed (e.g. start_year, end_year, reporting_periods)"
    )
    report_sections: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured sections of the research report"
    )
    claims: List[Claim] = Field(
        default_factory=list,
        description="All extracted and evaluated financial claims"
    )
    evidence_items: List[EvidenceItem] = Field(
        default_factory=list,
        description="All cited or evaluated evidence passages"
    )
    financial_calculations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Deterministic calculations performed during analysis"
    )
    judge_reviews: List[JudgeReview] = Field(
        default_factory=list,
        description="Full audit reviews from all three judges"
    )
    source_coverage: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of discovered vs missing sources and documentation gaps"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Consolidated warnings across the research run"
    )
    failed_nodes: List[str] = Field(
        default_factory=list,
        description="List of workflow nodes that encountered failures or timeouts"
    )
    created_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp of run creation"
    )
    completed_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp of run completion"
    )

    @field_validator("run_id")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only.")
        return stripped
