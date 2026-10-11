from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.certificate import CertificateStatus


class CertificateResponse(BaseModel):
    """Certificate summary and retrieval schema."""

    id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    course_name: Optional[str] = None
    status: CertificateStatus
    verification_code: str
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    download_url: Optional[str] = None
    download_pdf_url: Optional[str] = None
    download_png_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateVerifyResponse(BaseModel):
    """Public certificate verification response schema."""

    valid: bool
    certificate_id: Optional[str] = None
    verification_code: Optional[str] = None
    recipient_name: Optional[str] = None
    title: Optional[str] = None
    issuer_name: Optional[str] = None
    signatory_name: Optional[str] = None
    signatory_title: Optional[str] = None
    event_date: Optional[str] = None
    issue_date: Optional[datetime] = None
    status: Optional[str] = None
    message: str = "Certificate verification status"
