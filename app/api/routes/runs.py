"""Research run endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.requests import ResearchRequest, RunCreationResponse
from app.schemas.results import ResearchResult, RunStatus
from app.storage.run_store import get_run_store

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.post(
    "",
    response_model=RunCreationResponse,
    status_code=status.HTTP_200_OK,
    summary="Create a new research run",
)
def create_run(request: ResearchRequest) -> RunCreationResponse:
    """Queues a new financial research run with validated inputs.

    Accepts Mode A ('company') or Mode B ('upload') parameters.
    """
    store = get_run_store()
    run_id = store.create_run(request)
    return RunCreationResponse(run_id=run_id, status="queued")


@router.get(
    "/{run_id}",
    response_model=RunStatus,
    summary="Get research run status",
)
def get_run_status(run_id: str) -> RunStatus:
    """Retrieves current execution status and stage for a given run_id."""
    store = get_run_store()
    run_status = store.get_status(run_id)
    if not run_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )
    return run_status


@router.get(
    "/{run_id}/result",
    response_model=ResearchResult,
    summary="Get final research result",
)
def get_run_result(run_id: str) -> ResearchResult:
    """Retrieves final research report and validation outputs for a given run_id.

    Returns a clearly labelled mock payload during initial development.
    """
    store = get_run_store()
    result = store.get_result(run_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Result for run '{run_id}' not found.",
        )
    return result
