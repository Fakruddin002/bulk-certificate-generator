"""Generation job SQLAlchemy model matching assignment architecture."""
import enum
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


def get_utc_now():
    return datetime.now(timezone.utc)


class GenerationJob(Base):
    """Represents a batch certificate generation request job."""

    __tablename__ = "generation_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    issuer_name = Column(String(255), nullable=False, default="Global Certification Authority")
    signatory_name = Column(String(255), nullable=True, default="Director of Certification")
    signatory_title = Column(String(255), nullable=True, default="Authorized Signatory")
    event_date = Column(String(100), nullable=True)
    
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    
    total_records = Column(Integer, default=0, nullable=False)
    valid_records = Column(Integer, default=0, nullable=False)
    invalid_records = Column(Integer, default=0, nullable=False)
    processed_records = Column(Integer, default=0, nullable=False)
    successful_records = Column(Integer, default=0, nullable=False)
    failed_records = Column(Integer, default=0, nullable=False)
    
    error_summary = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # One-to-many relationship with individual Certificate records
    certificates = relationship("Certificate", back_populates="job", cascade="all, delete-orphan", lazy="selectin")

    @property
    def job_name(self) -> str:
        return self.title

    @property
    def total_recipients(self) -> int:
        return self.total_records

    @property
    def successful_count(self) -> int:
        return self.successful_records

    @property
    def failed_count(self) -> int:
        return self.failed_records
