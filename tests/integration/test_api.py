"""Integration tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """GET /api/health returns status ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_run_valid_company_mode():
    """POST /api/runs creates a run and returns queued status."""
    payload = {
        "input_mode": "company",
        "company_name": "Example Corp",
        "ticker": "EXMP",
        "jurisdiction": "US",
        "start_year": 2023,
        "end_year": 2025,
        "question": "Analyze revenue, cash flow and debt risks.",
        "requested_analyses": [
            "financial_performance",
            "cash_flow",
            "debt_and_liquidity",
            "business_risks",
        ],
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "queued"


def test_create_run_valid_upload_mode():
    """POST /api/runs creates a run in upload mode with document IDs."""
    payload = {
        "input_mode": "upload",
        "company_name": "Example Corp",
        "question": "Analyze debt metrics.",
        "document_ids": ["doc_uploaded_001"],
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "queued"


def test_create_run_invalid_empty_company():
    """POST /api/runs returns 422 for empty company name."""
    payload = {
        "input_mode": "company",
        "company_name": "   ",
        "question": "Analyze financial performance.",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 422


def test_create_run_invalid_date_range():
    """POST /api/runs returns 422 when start_year > end_year."""
    payload = {
        "company_name": "Example Corp",
        "question": "Analyze financial performance.",
        "start_year": 2025,
        "end_year": 2020,
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 422


def test_create_run_upload_mode_missing_documents():
    """POST /api/runs returns 422 in upload mode without document IDs."""
    payload = {
        "input_mode": "upload",
        "company_name": "Example Corp",
        "question": "Analyze financial performance.",
        "document_ids": [],
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 422


def test_get_run_status_seeded():
    """GET /api/runs/run_001 returns seeded mock run status consistent with mock result."""
    response = client.get("/api/runs/run_001")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "run_001"
    assert data["status"] == "completed_with_warnings"
    assert data["current_stage"] == "completed"
    assert isinstance(data["warnings"], list)


def test_get_run_status_newly_created():
    """GET /api/runs/{run_id} returns status consistent with immediately available mock result."""
    create_resp = client.post(
        "/api/runs",
        json={
            "company_name": "Dynamic Corp",
            "question": "What is the net profit margin?",
        },
    )
    assert create_resp.status_code == 200
    run_id = create_resp.json()["run_id"]

    status_resp = client.get(f"/api/runs/{run_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["run_id"] == run_id
    assert status_data["status"] == "completed_with_warnings"


def test_get_run_status_not_found():
    """GET /api/runs/{unknown_id} returns 404."""
    response = client.get("/api/runs/nonexistent_run_9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_run_result_mock():
    """GET /api/runs/{run_id}/result returns mock result with required schema fields."""
    response = client.get("/api/runs/run_001/result")
    assert response.status_code == 200
    result = response.json()
    assert result["run_id"] == "run_001"
    assert result["status"] == "completed_with_warnings"
    assert "company" in result
    assert "periods" in result
    assert "report_sections" in result
    assert "claims" in result
    assert "evidence_items" in result
    assert "judge_reviews" in result
    assert "warnings" in result
    # Ensure mock result is clearly labelled
    warnings_text = " ".join(result["warnings"])
    assert "MOCK RESULT" in warnings_text


def test_get_run_result_not_found():
    """GET /api/runs/{unknown_id}/result returns 404."""
    response = client.get("/api/runs/nonexistent_run_9999/result")
    assert response.status_code == 404


def test_mock_run_consistency_and_unverified_calculations():
    """Ensure run status matches research result status, and mock calculation/judges are unverified."""
    create_resp = client.post(
        "/api/runs",
        json={
            "company_name": "Integrity Corp",
            "question": "Verify debt to equity ratio.",
        },
    )
    assert create_resp.status_code == 200
    run_id = create_resp.json()["run_id"]

    status_data = client.get(f"/api/runs/{run_id}").json()
    result_data = client.get(f"/api/runs/{run_id}/result").json()

    # 1. Run status and Result status consistency
    assert status_data["status"] == result_data["status"]
    assert status_data["status"] == "completed_with_warnings"

    # 2. Mock calculations are NOT marked as verified
    calcs = result_data["financial_calculations"]
    assert len(calcs) > 0
    for calc in calcs:
        assert calc["verified"] is False
        assert "MOCK" in calc.get("explanation", "")
        assert calc.get("metadata", {}).get("mock") is True

    # 3. Mock judges do not imply real audits succeeded
    reviews = result_data["judge_reviews"]
    assert len(reviews) > 0
    for review in reviews:
        assert review["passed"] is False
        assert review["verdict"] == "unresolved"
        assert review["score"] is None
        assert "MOCK" in review["reasoning"]

    # 4. Mock claims are unevaluated without fabricated confidence
    claims = result_data["claims"]
    assert len(claims) > 0
    for claim in claims:
        assert claim["status"] == "not_evaluated"
        assert claim["confidence"] is None
        for role, verdict in claim["judge_verdicts"].items():
            assert verdict == "unresolved"
