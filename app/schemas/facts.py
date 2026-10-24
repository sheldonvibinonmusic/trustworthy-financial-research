"""Financial facts and calculation schemas."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class FinancialFact(BaseModel):
    """Structured financial fact extracted from corporate disclosures.

    Before comparing financial facts, validate company identity, period,
    unit, currency, accounting definition, reporting scope, and source version.
    """
    fact_id: str = Field(..., min_length=1, description="Unique fact identifier")
    company_name: str = Field(..., min_length=1, description="Company identity")
    ticker: Optional[str] = Field(default=None, description="Stock ticker symbol")
    metric_name: str = Field(..., min_length=1, description="Financial metric name (e.g. revenue, net_income)")
    value: float = Field(..., description="Numerical value extracted from source")
    period: str = Field(..., min_length=1, description="Reporting period (e.g. FY2023, Q3 2024)")
    unit: str = Field(..., min_length=1, description="Measurement unit (e.g. USD, millions, percentage)")
    currency: Optional[str] = Field(default="USD", description="Currency code (e.g. USD, EUR, GBP)")
    accounting_definition: str = Field(
        default="GAAP",
        description="Accounting standard used (e.g. GAAP, IFRS, Non-GAAP)"
    )
    reporting_scope: str = Field(
        default="consolidated",
        description="Reporting scope (e.g. consolidated, standalone, segment)"
    )
    source_version: str = Field(
        default="1.0",
        description="Source document version for provenance tracking"
    )
    document_id: Optional[str] = Field(default=None, description="Source document ID")
    page_number: Optional[int] = Field(default=None, ge=1, description="Source page number")
    evidence_id: Optional[str] = Field(default=None, description="Cross-referenced evidence snippet ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context or extraction metadata")

    @field_validator("fact_id", "company_name", "metric_name", "period", "unit")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only.")
        return stripped


class FinancialCalculation(BaseModel):
    """Deterministic financial calculation record derived from structured facts."""
    calculation_id: str = Field(..., min_length=1, description="Unique calculation identifier")
    metric_name: str = Field(..., min_length=1, description="Computed metric name (e.g. gross_margin, debt_to_equity)")
    formula: str = Field(..., min_length=1, description="Deterministic formula applied")
    input_fact_ids: List[str] = Field(default_factory=list, description="IDs of source FinancialFacts used")
    calculated_value: float = Field(..., description="Deterministically calculated result")
    unit: str = Field(default="USD", description="Unit of the calculated metric")
    period: str = Field(default="", description="Period covering the calculation")
    verified: bool = Field(default=True, description="Whether deterministic calculation passed consistency checks")
    explanation: Optional[str] = Field(default=None, description="Step-by-step arithmetic explanation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Calculation metadata")
