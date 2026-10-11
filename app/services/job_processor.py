"""Background job processing service module matching assignment specification."""
from typing import Optional, List, Any
from sqlalchemy.orm import Session
from app.services.job_service import JobService


def process_generation_job(job_id: str, recipients: Optional[List[Any]] = None, db: Optional[Session] = None) -> None:
    """
    Executes generation for all recipients in a job with fault isolation.
    Matches the conceptual function signature defined in Section 6 of the assignment PDF.
    """
    JobService.process_job(job_id=job_id, db=db)


__all__ = ["process_generation_job", "JobService"]
