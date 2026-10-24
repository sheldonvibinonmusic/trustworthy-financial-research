"""Document schemas for tracking ingested and discovered financial files."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class DocumentStatus(str, Enum):
    """Lifecycle status of a document record."""
    UPLOADED = "uploaded"
    PARSED = "parsed"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentRecord(BaseModel):
    """Metadata record for an uploaded or discovered financial document."""
    document_id: str = Field(..., min_length=1, description="Unique identifier for the document")
    filename: str = Field(..., min_length=1, description="Original filename or document title")
    status: str = Field(default=DocumentStatus.UPLOADED.value, description="Current ingestion status")
    company_name: Optional[str] = Field(default=None, description="Associated company name")
    reporting_period: Optional[str] = Field(default=None, description="Reporting period (e.g. FY2023, Q3 2024)")
    fiscal_year: Optional[int] = Field(default=None, description="Fiscal year if identified")
    doc_type: Optional[str] = Field(default=None, description="Document type (e.g. 10-K, 10-Q, annual_report)")
    version: str = Field(default="1.0", description="Document version for provenance tracking")
    page_count: Optional[int] = Field(default=None, ge=1, description="Total number of pages")
    source_url: Optional[str] = Field(default=None, description="Remote source URL if discovered")
    warnings: List[str] = Field(default_factory=list, description="Parsing or ingestion warnings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary layout or provenance metadata")
    created_at: Optional[datetime] = Field(default=None, description="Timestamp of document ingestion")

    @field_validator("document_id", "filename")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only.")
        return stripped


class DocumentUploadResponse(BaseModel):
    """API response for document upload endpoint."""
    documents: List[DocumentRecord] = Field(default_factory=list, description="List of processed document records")
