"""Request schemas for the financial research system."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class InputMode(str, Enum):
    """Supported input modes for research runs."""
    COMPANY = "company"
    UPLOAD = "upload"


class RequestedAnalysis(str, Enum):
    """Standard requested analysis categories."""
    FINANCIAL_PERFORMANCE = "financial_performance"
    CASH_FLOW = "cash_flow"
    DEBT_AND_LIQUIDITY = "debt_and_liquidity"
    BUSINESS_RISKS = "business_risks"


class ResearchRequest(BaseModel):
    """Parameters required to initiate a financial research run."""
    input_mode: InputMode = Field(
        default=InputMode.COMPANY,
        description="Mode A ('company') or Mode B ('upload')"
    )
    company_name: str = Field(
        ...,
        min_length=1,
        description="Name of the target company"
    )
    ticker: Optional[str] = Field(
        default=None,
        description="Stock ticker symbol where applicable"
    )
    jurisdiction: Optional[str] = Field(
        default="US",
        description="Reporting jurisdiction (e.g. US, UK, EU)"
    )
    start_year: Optional[int] = Field(
        default=None,
        description="Start year for financial analysis scope"
    )
    end_year: Optional[int] = Field(
        default=None,
        description="End year for financial analysis scope"
    )
    question: str = Field(
        ...,
        min_length=1,
        description="Target research question or objective"
    )
    document_ids: List[str] = Field(
        default_factory=list,
        description="Document identifiers relevant to this research run"
    )
    requested_analyses: List[str] = Field(
        default_factory=lambda: [
            RequestedAnalysis.FINANCIAL_PERFORMANCE.value,
            RequestedAnalysis.CASH_FLOW.value,
            RequestedAnalysis.DEBT_AND_LIQUIDITY.value,
            RequestedAnalysis.BUSINESS_RISKS.value,
        ],
        description="List of analysis modules requested"
    )

    @field_validator("company_name", "question")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only.")
        return stripped

    @model_validator(mode="after")
    def validate_request(self) -> "ResearchRequest":
        if self.start_year is not None and self.end_year is not None:
            if self.start_year > self.end_year:
                raise ValueError(
                    f"start_year ({self.start_year}) cannot be greater than end_year ({self.end_year})."
                )
        if self.input_mode == InputMode.UPLOAD and not self.document_ids:
            raise ValueError(
                "document_ids must be provided when input_mode is 'upload'."
            )
        return self


class RunCreationResponse(BaseModel):
    """Response returned upon successfully queueing a research run."""
    run_id: str = Field(..., description="Unique identifier for the research run")
    status: str = Field(default="queued", description="Initial lifecycle status")
