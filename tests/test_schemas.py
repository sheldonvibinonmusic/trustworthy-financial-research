"""Tests for core Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    Claim,
    ClaimStatus,
    DocumentRecord,
    DocumentStatus,
    EvidenceItem,
    FinancialFact,
    InputMode,
    JudgeReview,
    JudgeRole,
    JudgeVerdict,
    ResearchRequest,
    ResearchResult,
    RunStatus,
    RunStatusState,
)


def test_research_request_valid_company_mode():
    """Test valid ResearchRequest in Mode A (company)."""
    req = ResearchRequest(
        input_mode=InputMode.COMPANY,
        company_name="Acme Corp",
        ticker="ACME",
        jurisdiction="US",
        start_year=2022,
        end_year=2024,
        question="What is the free cash flow trend?",
    )
    assert req.company_name == "Acme Corp"
    assert req.ticker == "ACME"
    assert req.start_year == 2022
    assert req.end_year == 2024
    assert len(req.requested_analyses) > 0


def test_research_request_valid_upload_mode():
    """Test valid ResearchRequest in Mode B (upload)."""
    req = ResearchRequest(
        input_mode=InputMode.UPLOAD,
        company_name="Acme Corp",
        question="Analyze the 10-K risk factors.",
        document_ids=["doc_10k_2024"],
    )
    assert req.input_mode == InputMode.UPLOAD
    assert req.document_ids == ["doc_10k_2024"]


def test_research_request_invalid_years():
    """Test start_year > end_year raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        ResearchRequest(
            company_name="Acme Corp",
            question="Analyze revenue.",
            start_year=2025,
            end_year=2023,
        )
    assert "start_year (2025) cannot be greater than end_year (2023)" in str(exc_info.value)


def test_research_request_empty_company():
    """Test empty company_name raises validation error."""
    with pytest.raises(ValidationError):
        ResearchRequest(
            company_name="   ",
            question="Analyze revenue.",
        )


def test_research_request_upload_mode_missing_document_ids():
    """Test Mode B with missing document_ids raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        ResearchRequest(
            input_mode=InputMode.UPLOAD,
            company_name="Acme Corp",
            question="Analyze revenue.",
            document_ids=[],
        )
    assert "document_ids must be provided when input_mode is 'upload'" in str(exc_info.value)


def test_document_record_schema():
    """Test DocumentRecord instantiation and defaults."""
    doc = DocumentRecord(
        document_id="doc_001",
        filename="annual_report_2024.pdf",
        status=DocumentStatus.UPLOADED,
        company_name="Acme Corp",
        reporting_period="FY2024",
        fiscal_year=2024,
        doc_type="10-K",
        version="1.0",
        page_count=120,
    )
    assert doc.document_id == "doc_001"
    assert doc.filename == "annual_report_2024.pdf"
    assert doc.page_count == 120
    assert doc.warnings == []


def test_evidence_item_schema():
    """Test EvidenceItem instantiation and location tracking."""
    evi = EvidenceItem(
        evidence_id="evi_001",
        document_id="doc_001",
        document_version="1.0",
        page_number=45,
        section_title="Item 7. Management Discussion and Analysis",
        text="Operating revenues expanded 14% year-over-year to $4.2B.",
        snippet_type="text",
        score=0.91,
        is_counter_evidence=False,
    )
    assert evi.evidence_id == "evi_001"
    assert evi.page_number == 45
    assert not evi.is_counter_evidence


def test_financial_fact_schema():
    """Test FinancialFact fields required for cross-period and unit validation."""
    fact = FinancialFact(
        fact_id="fact_001",
        company_name="Acme Corp",
        ticker="ACME",
        metric_name="operating_cash_flow",
        value=1500.5,
        period="FY2024",
        unit="millions",
        currency="USD",
        accounting_definition="GAAP",
        reporting_scope="consolidated",
        source_version="1.0",
        document_id="doc_001",
        page_number=52,
    )
    assert fact.metric_name == "operating_cash_flow"
    assert fact.value == 1500.5
    assert fact.currency == "USD"
    assert fact.accounting_definition == "GAAP"
    assert fact.reporting_scope == "consolidated"


def test_claim_schema():
    """Test Claim schema with statuses and citations."""
    claim = Claim(
        claim_id="claim_001",
        statement="Acme Corp generated $1.5B in operating cash flow in FY2024.",
        status=ClaimStatus.VERIFIED_SOURCE,
        evidence_ids=["evi_001"],
        calculation_ids=[],
        confidence=0.98,
        reasoning="Directly cited from FY2024 Cash Flow Statement.",
    )
    assert claim.status == ClaimStatus.VERIFIED_SOURCE
    assert "evi_001" in claim.evidence_ids
    assert claim.confidence == 0.98


def test_claim_invalid_status():
    """Test that invalid claim statuses fail schema validation."""
    with pytest.raises(ValidationError):
        Claim(
            claim_id="claim_002",
            statement="Test statement",
            status="invalid_status_value",  # type: ignore
        )


def test_judge_review_schema():
    """Test JudgeReview with auditor verdict and details."""
    review = JudgeReview(
        review_id="rev_001",
        judge_role=JudgeRole.EVIDENCE_CITATION_AUDITOR.value,
        claim_id="claim_001",
        verdict=JudgeVerdict.PASS.value,
        passed=True,
        score=0.95,
        evidence_ids=["evi_001"],
        counter_evidence_ids=[],
        reasoning="The cited passage explicitly mentions $1.5B operating cash flow.",
        inconsistencies_found=[],
    )
    assert review.passed is True
    assert review.judge_role == "evidence_citation_auditor"
    assert review.verdict == "pass"


def test_run_status_schema():
    """Test RunStatus response model."""
    status_obj = RunStatus(
        run_id="run_001",
        status=RunStatusState.RUNNING,
        current_stage="retrieval",
        progress=0.45,
        warnings=[],
    )
    assert status_obj.run_id == "run_001"
    assert status_obj.status == RunStatusState.RUNNING
    assert status_obj.current_stage == "retrieval"


def test_research_result_schema():
    """Test ResearchResult model serialization."""
    result = ResearchResult(
        run_id="run_001",
        status=RunStatusState.COMPLETED_WITH_WARNINGS,
        company={"company_name": "Acme Corp"},
        periods={"start_year": 2023, "end_year": 2024},
        report_sections=[
            {"section_id": "sec_1", "title": "Overview", "content": "Sample content."}
        ],
        claims=[
            Claim(
                claim_id="c1",
                statement="Revenue grew 10%",
                status=ClaimStatus.NOT_EVALUATED,
            )
        ],
        evidence_items=[
            EvidenceItem(
                evidence_id="e1",
                document_id="doc_1",
                text="Revenue grew 10% in 2024.",
            )
        ],
        financial_calculations=[],
        judge_reviews=[],
        source_coverage={"coverage": "complete"},
        warnings=["Test warning"],
        failed_nodes=[],
    )
    assert result.run_id == "run_001"
    assert len(result.claims) == 1
    assert len(result.evidence_items) == 1
    dumped = result.model_dump()
    assert dumped["run_id"] == "run_001"
    assert dumped["status"] == "completed_with_warnings"
