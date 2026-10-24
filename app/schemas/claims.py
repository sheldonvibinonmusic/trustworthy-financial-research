"""Claim, evidence, and judge review schemas."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ClaimStatus(str, Enum):
    """Permitted verification statuses for financial claims."""
    VERIFIED_SOURCE = "verified_source"
    CALCULATED_CHECKED = "calculated_checked"
    INTERPRETATION_SUPPORTED = "interpretation_supported"
    UNRESOLVED = "unresolved"
    BLOCKED = "blocked"
    NOT_EVALUATED = "not_evaluated"


class JudgeRole(str, Enum):
    """Roles for the three specialized LLM judges."""
    EVIDENCE_CITATION_AUDITOR = "evidence_citation_auditor"
    FINANCIAL_INTEGRITY_AUDITOR = "financial_integrity_auditor"
    ADVERSARIAL_SKEPTIC = "adversarial_skeptic"


class JudgeVerdict(str, Enum):
    """Standardized verdicts from judges."""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    ABSTAIN = "abstain"
    UNRESOLVED = "unresolved"


class EvidenceItem(BaseModel):
    """Retrieved evidence passage preserving document provenance and location."""
    evidence_id: str = Field(..., min_length=1, description="Unique evidence identifier")
    document_id: str = Field(..., min_length=1, description="Source document identifier")
    document_version: str = Field(default="1.0", description="Source document version")
    page_number: Optional[int] = Field(default=None, ge=1, description="Source page number")
    section_title: Optional[str] = Field(default=None, description="Heading or section title where text appears")
    text: str = Field(..., min_length=1, description="Passage or snippet text")
    snippet_type: str = Field(default="text", description="Type of snippet: text, table, or footnote")
    score: Optional[float] = Field(default=None, description="Retrieval / reranker relevance score")
    is_counter_evidence: bool = Field(default=False, description="Whether this passage constitutes counter-evidence")
    table_context: Optional[Dict[str, Any]] = Field(default=None, description="Contextual headers/footnotes if a table")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional retrieval metadata")

    @field_validator("evidence_id", "document_id", "text")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only.")
        return stripped


class JudgeReview(BaseModel):
    """Structured evaluation report returned by an LLM judge."""
    review_id: str = Field(..., min_length=1, description="Unique review identifier")
    judge_role: str = Field(..., min_length=1, description="Role of the judge conducting review")
    claim_id: Optional[str] = Field(default=None, description="Associated claim identifier")
    verdict: str = Field(default=JudgeVerdict.UNRESOLVED.value, description="Structured verdict")
    passed: bool = Field(default=False, description="Whether the claim passed this judge's audit")
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence_ids: List[str] = Field(default_factory=list, description="IDs of supporting evidence reviewed")
    counter_evidence_ids: List[str] = Field(default_factory=list, description="IDs of counter-evidence identified")
    reasoning: str = Field(..., min_length=1, description="Detailed explanation of the verdict")
    inconsistencies_found: List[str] = Field(default_factory=list, description="List of identified discrepancies")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Audit execution metadata")

    @field_validator("review_id", "judge_role", "reasoning")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only.")
        return stripped


class Claim(BaseModel):
    """Financial claim with provenance references and multi-judge verification status."""
    claim_id: str = Field(..., min_length=1, description="Unique claim identifier")
    statement: str = Field(..., min_length=1, description="Factual or analytical assertion")
    status: ClaimStatus = Field(
        default=ClaimStatus.NOT_EVALUATED,
        description="Current verification status of the claim"
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="Citations supporting this claim"
    )
    calculation_ids: List[str] = Field(
        default_factory=list,
        description="Deterministic calculations validating this claim"
    )
    judge_verdicts: Dict[str, Any] = Field(
        default_factory=dict,
        description="Individual verdicts from each of the three judges"
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="System confidence score for this claim"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Summary synthesis explaining the verification outcome"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings regarding evidence quality, missing data, or conflicts"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Claim metadata and tracking details"
    )

    @field_validator("claim_id", "statement")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only.")
        return stripped
