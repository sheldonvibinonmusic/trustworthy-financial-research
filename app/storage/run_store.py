"""In-memory storage and mock generator for research runs.

Provides a thread-safe mock store that satisfies API contracts for run creation,
status polling, and mock result retrieval before full LangGraph orchestration is wired.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, Optional
import uuid

from app.schemas.claims import Claim, ClaimStatus, EvidenceItem, JudgeReview, JudgeRole, JudgeVerdict
from app.schemas.requests import InputMode, ResearchRequest
from app.schemas.results import ResearchResult, RunStatus, RunStatusState


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_mock_research_result(run_id: str, request: ResearchRequest) -> ResearchResult:
    """Constructs a clearly labelled mock ResearchResult satisfying schema contracts."""
    doc_id = request.document_ids[0] if request.document_ids else "doc_mock_001"
    now_iso = _utc_now_iso()

    mock_evidence = EvidenceItem(
        evidence_id="evi_mock_001",
        document_id=doc_id,
        document_version="1.0",
        page_number=1,
        section_title="Financial Highlights (Mock)",
        text=f"MOCK EVIDENCE: Disclosed financial statements for {request.company_name}.",
        snippet_type="text",
        score=0.92,
        is_counter_evidence=False,
        metadata={"note": "mock evidence item for contract verification"}
    )

    mock_claim = Claim(
        claim_id="claim_mock_001",
        statement=f"MOCK: {request.company_name} maintains positive operating cash flow for requested periods.",
        status=ClaimStatus.NOT_EVALUATED,
        evidence_ids=["evi_mock_001"],
        calculation_ids=["calc_mock_001"],
        judge_verdicts={
            "evidence_citation_auditor": JudgeVerdict.UNRESOLVED.value,
            "financial_integrity_auditor": JudgeVerdict.UNRESOLVED.value,
            "adversarial_skeptic": JudgeVerdict.UNRESOLVED.value,
        },
        confidence=None,
        reasoning="MOCK CLAIM: Synthesized placeholder claim pending active multi-judge evaluation.",
        warnings=["MOCK: Multi-judge verification pipeline not yet active; claim is not evaluated."],
        metadata={"source": "mock_generator", "evaluated": False}
    )

    mock_judge_review = JudgeReview(
        review_id="rev_mock_001",
        judge_role=JudgeRole.EVIDENCE_CITATION_AUDITOR.value,
        claim_id="claim_mock_001",
        verdict=JudgeVerdict.UNRESOLVED.value,
        passed=False,
        score=None,
        evidence_ids=["evi_mock_001"],
        counter_evidence_ids=[],
        reasoning="MOCK REVIEW: Automated LLM judges have not yet executed. Review verdict is unresolved.",
        inconsistencies_found=["MOCK: Real audit not performed; placeholder judge review."],
        metadata={"judge_model": "mock_auditor", "executed": False}
    )

    return ResearchResult(
        run_id=run_id,
        status=RunStatusState.COMPLETED_WITH_WARNINGS,
        company={
            "company_name": request.company_name,
            "ticker": request.ticker,
            "jurisdiction": request.jurisdiction,
        },
        periods={
            "start_year": request.start_year,
            "end_year": request.end_year,
        },
        report_sections=[
            {
                "section_id": "sec_mock_001",
                "title": "Mock Financial Overview",
                "content": f"MOCK REPORT: Research evaluation for {request.company_name}. "
                           "Full deterministic calculations and multi-judge reviews will populate here.",
                "claim_ids": ["claim_mock_001"],
                "warnings": ["MOCK DATA: Generated for schema and API contract validation."],
            }
        ],
        claims=[mock_claim],
        evidence_items=[mock_evidence],
        financial_calculations=[
            {
                "calculation_id": "calc_mock_001",
                "metric_name": "mock_operating_margin",
                "formula": "operating_income / revenue",
                "calculated_value": 0.18,
                "unit": "ratio",
                "period": f"{request.start_year or 2023}-{request.end_year or 2025}",
                "verified": False,
                "explanation": "MOCK CALCULATION: Placeholder calculation; not verified against verified source financial facts.",
                "metadata": {
                    "mock": True,
                    "note": "Unverified mock calculation pending deterministic calculation engine implementation."
                },
            }
        ],
        judge_reviews=[mock_judge_review],
        source_coverage={
            "status": "mock_coverage",
            "requested_documents": request.document_ids,
            "covered_count": len(request.document_ids),
            "missing_disclosures": [],
        },
        warnings=[
            "MOCK RESULT: Multi-agent workflow and LLM judges not yet executed. "
            "This mock response validates schema integrity and API contracts."
        ],
        failed_nodes=[],
        created_at=now_iso,
        completed_at=now_iso,
    )


class RunStore:
    """Thread-safe in-memory store for research runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: Dict[str, RunStatus] = {}
        self._results: Dict[str, ResearchResult] = {}
        self._requests: Dict[str, ResearchRequest] = {}
        self._seed_default_mock_run()

    def _seed_default_mock_run(self) -> None:
        """Seeds default 'run_001' to support contract examples out of the box."""
        default_req = ResearchRequest(
            input_mode=InputMode.COMPANY,
            company_name="Example Company",
            ticker="EXAMPLE",
            jurisdiction="US",
            start_year=2023,
            end_year=2025,
            question="Analyze revenue, cash flow and debt risks.",
            document_ids=["doc_001"],
        )
        self._requests["run_001"] = default_req
        self._runs["run_001"] = RunStatus(
            run_id="run_001",
            status=RunStatusState.COMPLETED_WITH_WARNINGS,
            current_stage="completed",
            progress=1.0,
            warnings=[
                "MOCK: Default seeded contract test run completed with mock result. "
                "Background workflow orchestration is not active."
            ],
        )
        self._results["run_001"] = build_mock_research_result("run_001", default_req)

    def create_run(self, request: ResearchRequest) -> str:
        """Initializes a new run and stores a corresponding mock result."""
        with self._lock:
            run_id = f"run_{uuid.uuid4().hex[:8]}"
            self._requests[run_id] = request
            self._runs[run_id] = RunStatus(
                run_id=run_id,
                status=RunStatusState.COMPLETED_WITH_WARNINGS,
                current_stage="completed",
                progress=1.0,
                warnings=[
                    "MOCK: Run completed immediately with mock data. "
                    "Background workflow orchestration is not active."
                ],
            )
            self._results[run_id] = build_mock_research_result(run_id, request)
            return run_id

    def get_status(self, run_id: str) -> Optional[RunStatus]:
        """Retrieves the status for a given run_id."""
        with self._lock:
            return self._runs.get(run_id)

    def get_result(self, run_id: str) -> Optional[ResearchResult]:
        """Retrieves the mock research result for a given run_id."""
        with self._lock:
            return self._results.get(run_id)


# Global singleton instance
_GLOBAL_STORE = RunStore()


def get_run_store() -> RunStore:
    """Returns the singleton RunStore instance."""
    return _GLOBAL_STORE
