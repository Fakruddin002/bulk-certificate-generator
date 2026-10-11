"""Certificate-related API endpoints for listing, retrieval, and verification."""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.certificate import CertificateResponse, CertificateVerifyResponse
from app.services.job_service import JobService
from app.services.storage_service import StorageService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    summary="List, search and filter certificates",
    description="Query certificates with optional filters for job_id, status, recipient name/email/verification code search.",
)
def list_certificates(
    request: Request,
    job_id: Optional[str] = Query(None, description="Filter by generation job ID"),
    status: Optional[str] = Query(None, description="Filter by status (PENDING, GENERATING, SUCCESS, FAILED)"),
    search: Optional[str] = Query(None, description="Search recipient name, email, or verification code"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    db: Session = Depends(get_db),
):
    total, certs = JobService.list_certificates(
        db=db, job_id=job_id, status=status, search=search, skip=skip, limit=limit
    )
    base_url = str(request.base_url).rstrip("/")
    items = [JobService.format_certificate_response(c, base_url=base_url) for c in certs]
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "certificates": items,
    }


@router.get(
    "/{certificate_id}",
    response_model=CertificateResponse,
    summary="Get single certificate details",
    description="Retrieve status and metadata of a specific certificate.",
)
def get_certificate_details(
    certificate_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    cert = JobService.get_certificate(db, certificate_id=certificate_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate with ID '{certificate_id}' not found.",
        )

    base_url = str(request.base_url).rstrip("/")
    return JobService.format_certificate_response(cert, base_url=base_url)


@router.get(
    "/{certificate_id}/download",
    response_class=FileResponse,
    summary="Download certificate in PDF or PNG format",
    description="Retrieve and stream the generated certificate for a recipient. Supports '?format=pdf' or '?format=png'.",
)
def download_certificate(
    certificate_id: str,
    format: str = Query("pdf", description="Certificate format: 'pdf' or 'png'"),
    db: Session = Depends(get_db),
):
    cert = JobService.get_certificate(db, certificate_id=certificate_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate with ID '{certificate_id}' not found.",
        )

    if cert.status.value != "SUCCESS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Certificate is in '{cert.status.value}' state and not ready for download. Error: {cert.error_message or 'None'}",
        )

    return StorageService.get_certificate_file_response(cert, format=format)


@router.get(
    "/{certificate_id}/download/pdf",
    response_class=FileResponse,
    summary="Download certificate PDF directly",
    description="Explicit direct endpoint to download the certificate as a PDF file.",
)
def download_certificate_pdf_direct(
    certificate_id: str,
    db: Session = Depends(get_db),
):
    return download_certificate(certificate_id=certificate_id, format="pdf", db=db)


@router.get(
    "/{certificate_id}/download/png",
    response_class=FileResponse,
    summary="Download certificate PNG directly",
    description="Explicit direct endpoint to download the certificate as a high-resolution PNG image.",
)
def download_certificate_png_direct(
    certificate_id: str,
    db: Session = Depends(get_db),
):
    return download_certificate(certificate_id=certificate_id, format="png", db=db)


@router.get(
    "/verify/{verification_code}",
    response_model=CertificateVerifyResponse,
    summary="Verify certificate authenticity",
    description="Public endpoint to verify certificate legitimacy using its unique verification code.",
)
def verify_certificate(
    verification_code: str,
    db: Session = Depends(get_db),
):
    cert = JobService.get_certificate_by_code(db, code=verification_code)
    if not cert or cert.status.value != "SUCCESS":
        return CertificateVerifyResponse(
            valid=False,
            verification_code=verification_code,
            message="Invalid certificate or certificate has not been successfully issued.",
        )

    job = cert.job
    return CertificateVerifyResponse(
        valid=True,
        certificate_id=cert.id,
        verification_code=cert.verification_code,
        recipient_name=cert.recipient_name,
        title=job.title if job else "N/A",
        issuer_name=job.issuer_name if job else "N/A",
        signatory_name=job.signatory_name if job else "N/A",
        signatory_title=job.signatory_title if job else "N/A",
        event_date=job.event_date if job else None,
        issue_date=cert.created_at,
        status="VALID",
        message="Certificate is authentic and valid.",
    )
