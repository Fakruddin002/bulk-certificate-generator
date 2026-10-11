"""Certificate record SQLAlchemy model matching assignment architecture."""
import enum
from datetime import datetime, timezone
import uuid
import secrets
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class CertificateStatus(str, enum.Enum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


def get_utc_now():
    return datetime.now(timezone.utc)


def generate_verification_code() -> str:
    """Generate a clean, secure verification code."""
    return f"CERT-{secrets.token_hex(4).upper()}"


class Certificate(Base):
    """Represents an individual certificate generated for a recipient."""

    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    job_id = Column(String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    recipient_name = Column(String(255), nullable=False, index=True)
    recipient_email = Column(String(255), nullable=False, index=True)
    course_name = Column(String(255), nullable=True)
    extra_data = Column(Text, nullable=True)  # JSON-encoded extra fields (score, grade, etc.)
    
    status = Column(Enum(CertificateStatus), default=CertificateStatus.PENDING, nullable=False, index=True)
    
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    verification_code = Column(String(64), unique=True, index=True, default=generate_verification_code, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationship back to GenerationJob
    job = relationship("GenerationJob", back_populates="certificates")


# CertificateRecord alias for exact PDF Table 2 nomenclature
CertificateRecord = Certificate
