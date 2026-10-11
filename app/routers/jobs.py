"""Job-related API endpoints for creation, progress tracking, and retrieval."""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.job import (
    JobCreateRequest,
    JobResponse,
    JobDetailResponse,
    JobListResponse,
)
from app.schemas.certificate import CertificateResponse
from app.services.job_service import JobService
from app.services.storage_service import StorageService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=JobDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a bulk certificate generation request",
    description="""
    Submit a bulk list of recipients with course/event information.
    By default, the job is dispatched to background workers for non-blocking asynchronous processing.
    Pass `?sync=true` if immediate synchronous generation is desired (e.g. for small testing batches).
    """,
)
def create_generation_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    sync: bool = Query(False, description="Process synchronously instead of in background"),
    db: Session = Depends(get_db),
):
    # 1. Validate & create initial DB records
    job, validation_failures = JobService.create_job(db=db, request=payload)
    base_url = str(request.base_url).rstrip("/")

    # 2. Process synchronously or in background
    if sync:
        JobService.process_job(job_id=job.id, db=db)
        refreshed_job = JobService.get_job(db, job.id)
        return JobService.format_job_detail_response(
            refreshed_job,
            validation_failures=validation_failures,
            base_url=base_url,
        )
    else:
        background_tasks.add_task(JobService.process_job, job_id=job.id)
        return JobService.format_job_detail_response(
            job,
            validation_failures=validation_failures,
            base_url=base_url,
        )


@router.get(
    "/stats/overview",
    summary="Get system and dashboard statistics",
    description="Aggregate statistics of total jobs, certificates, success rate, and recent activity for the UI dashboard.",
)
def get_dashboard_stats(
    db: Session = Depends(get_db),
):
    return JobService.get_system_stats(db)


@router.post(
    "/seed-test-scenarios",
    response_model=List[JobResponse],
    summary="Seed comprehensive test case scenarios",
    description="Automatically generates and processes all 3 distinct test case jobs: 1) All Pass (100% Success), 2) Some Failed (Fault Isolation), and 3) All Failed.",
)
def seed_test_scenarios_endpoint(
    request: Request,
    clear_existing: bool = Query(False, description="Clear existing jobs before generating test cases"),
    db: Session = Depends(get_db),
):
    base_url = str(request.base_url).rstrip("/")
    return JobService.seed_test_scenarios(db=db, clear_existing=clear_existing, base_url=base_url)


@router.get(
    "/{job_id}",
    response_model=JobDetailResponse,
    summary="Get generation job status and progress",
    description="Check the real-time progress, status, statistics, and certificate records of a job.",
)
def get_job_status(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    job = JobService.get_job(db, job_id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    base_url = str(request.base_url).rstrip("/")
    return JobService.format_job_detail_response(job, base_url=base_url)


@router.get(
    "/{job_id}/certificates",
    response_model=List[CertificateResponse],
    summary="List certificates and their individual statuses",
    description="List all recipient certificate records and their individual statuses for a specific job as required in assignment specification.",
)
def get_job_certificates(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    job = JobService.get_job(db, job_id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    base_url = str(request.base_url).rstrip("/")
    return [JobService.format_certificate_response(c, base_url=base_url) for c in (job.certificates or [])]


@router.get(
    "",
    response_model=JobListResponse,
    summary="List certificate generation jobs",
    description="Retrieve paginated list of all generation jobs ordered newest first.",
)
def list_generation_jobs(
    request: Request,
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    db: Session = Depends(get_db),
):
    total, jobs = JobService.list_jobs(db, skip=skip, limit=limit)
    base_url = str(request.base_url).rstrip("/")
    formatted_jobs = [JobService.format_job_response(j, base_url=base_url) for j in jobs]
    return JobListResponse(total=total, jobs=formatted_jobs)


@router.get(
    "/{job_id}/download-all",
    response_class=FileResponse,
    summary="Download all generated certificates as a ZIP archive",
    description="Packages all successfully generated certificates for a job into a ZIP file. Supports '?format=pdf', '?format=png', or '?format=all'.",
)
def download_all_job_certificates(
    job_id: str,
    format: str = Query("pdf", description="ZIP archive format: 'pdf', 'png', or 'all'"),
    db: Session = Depends(get_db),
):
    job = JobService.get_job(db, job_id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    successful_certs = [c for c in job.certificates if c.status.value == "SUCCESS"]
    if not successful_certs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_id}' does not have any successfully generated certificates to download yet.",
        )

    clean_format = (format or "pdf").lower().strip()
    zip_path = StorageService.create_job_zip_archive(
        job_id=job.id, certificates=successful_certs, format=clean_format
    )
    zip_filename = f"certificates_{job.title.replace(' ', '_')}_{job.id}_{clean_format}.zip"

    return FileResponse(
        path=str(zip_path),
        filename=zip_filename,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
