import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func

from api.schemas import (
    CreateSessionRequest,
    SessionResponse,
    SessionDetailResponse,
    SessionListResponse,
    SuccessResponse,
    PaginationParams,
)
from db.models import ResearchSession
from db.repository import SessionRepository, get_session_repo

router = APIRouter()


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: CreateSessionRequest,
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.create(
        company_name=payload.company_name,
        website=payload.website,
        objective=payload.objective,
    )
    return session


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    params: PaginationParams = Depends(),
    repo: SessionRepository = Depends(get_session_repo),
):
    sessions = await repo.get_all(limit=params.limit, offset=params.offset)

    # Fetch total count for pagination metadata
    count_stmt = select(func.count(ResearchSession.id)).where(ResearchSession.is_active == True)
    count_result = await repo.db.execute(count_stmt)
    total_count = count_result.scalar_one()

    return SessionListResponse(
        items=[SessionResponse.model_validate(s) for s in sessions],
        total=total_count,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/{id}", response_model=SessionDetailResponse)
async def get_session(
    id: uuid.UUID,
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.get_by_id(id, load_relations=True)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found with id: {id}",
        )
    return session


@router.delete("/{id}", response_model=SuccessResponse)
async def delete_session(
    id: uuid.UUID,
    repo: SessionRepository = Depends(get_session_repo),
):
    deleted = await repo.delete(id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found with id: {id}",
        )
    return SuccessResponse(message=f"Session {id} successfully deleted")
