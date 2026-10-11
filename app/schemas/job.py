from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.job import JobStatus
from app.schemas.recipient import RecipientInput, RecipientValidationFailure
from app.schemas.certificate import CertificateResponse


class JobCreateRequest(BaseModel):
    """Payload for submitting a bulk certificate generation job."""

    title: Optional[str] = Field(None, max_length=255, description="Title of course, workshop, or event")
    job_name: Optional[str] = Field(None, max_length=255, description="Alias for title / course name")
    course_name: Optional[str] = Field(None, max_length=255, description="Course or event name")
    description: Optional[str] = Field(None, max_length=1000, description="Optional brief description or achievement criteria")
    issuer_name: Optional[str] = Field(None, max_length=255, description="Name of issuing organization/company")
    signatory_name: Optional[str] = Field(None, max_length=255, description="Name of the official signatory")
    signatory_title: Optional[str] = Field(None, max_length=255, description="Designation/Title of signatory")
    event_date: Optional[str] = Field(None, max_length=100, description="Display date of the event/issue (e.g. 'October 24, 2026')")
    completion_date: Optional[str] = Field(None, max_length=100, description="Alias for event_date")
    
    recipients: List[RecipientInput] = Field(..., min_length=1, description="List of recipient details for certificate generation")

    @model_validator(mode="before")
    @classmethod
    def reconcile_names_and_dates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Check title, job_name, course_name
            t = data.get("title") or data.get("job_name") or data.get("course_name")
            if not t or not str(t).strip():
                raise ValueError("Job title or job_name cannot be empty")
            clean_title = str(t).strip()
            data["title"] = clean_title
            if not data.get("job_name"):
                data["job_name"] = clean_title
            if not data.get("course_name"):
                data["course_name"] = clean_title

            # Check date fields
            dt = data.get("event_date") or data.get("completion_date")
            if dt and str(dt).strip():
                data["event_date"] = str(dt).strip()
                data["completion_date"] = str(dt).strip()
        return data


class JobResponse(BaseModel):
    """High-level summary of a generation job and its current progress."""

    id: str
    job_id: Optional[str] = None
    title: str
    job_name: Optional[str] = None
    course_name: Optional[str] = None
    description: Optional[str] = None
    issuer_name: str
    status: JobStatus
    
    total_records: int
    total_recipients: Optional[int] = None
    valid_records: int
    invalid_records: int
    processed_records: int
    successful_records: int
    successful_count: Optional[int] = None
    failed_records: int
    failed_count: Optional[int] = None
    progress_percentage: float = 0.0
    message: Optional[str] = None
    
    error_summary: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    download_all_url: Optional[str] = None
    download_all_pdf_url: Optional[str] = None
    download_all_png_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JobDetailResponse(JobResponse):
    """Detailed view of a job including all individual certificate statuses and validation issues."""

    certificates: List[CertificateResponse] = Field(default_factory=list)
    validation_failures: List[RecipientValidationFailure] = Field(default_factory=list)


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    total: int
    jobs: List[JobResponse]
