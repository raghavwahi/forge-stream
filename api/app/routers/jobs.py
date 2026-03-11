"""Router for background job management endpoints."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_redis_provider
from app.models.user import UserInDB
from app.providers.redis import RedisProvider
from app.schemas.jobs import EnqueueJobRequest, Job, JobStatusResponse
from app.workers.job_queue import JobQueue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _get_queue(redis: RedisProvider = Depends(get_redis_provider)) -> JobQueue:
    return JobQueue(redis)


@router.post("", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_job(
    body: EnqueueJobRequest,
    queue: JobQueue = Depends(_get_queue),
    current_user: UserInDB = Depends(get_current_user),
) -> JobStatusResponse:
    """Enqueue a background job and return its initial status."""
    job = Job(type=body.type, payload=body.payload, owner_user_id=current_user.id)
    await queue.enqueue(job)
    return JobStatusResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        created_at=job.created_at,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    queue: JobQueue = Depends(_get_queue),
    current_user: UserInDB = Depends(get_current_user),
) -> JobStatusResponse:
    """Return the current status of a job by ID."""
    job = await queue.get_status(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    if job.owner_user_id is not None and job.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    return JobStatusResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        error=job.error,
        result=job.result,
        created_at=job.created_at,
    )
