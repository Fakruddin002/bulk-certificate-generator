import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.config import settings
from app.database import SessionLocal
from app.models.job import GenerationJob, JobStatus
from app.models.certificate import Certificate, CertificateStatus
from app.schemas.job import JobCreateRequest, JobResponse, JobDetailResponse
from app.schemas.certificate import CertificateResponse
from app.schemas.recipient import RecipientValidationFailure
from app.services.certificate_generator import CertificateGenerator

logger = logging.getLogger(__name__)


class JobService:
    """Service to coordinate bulk certificate generation jobs."""

    @staticmethod
    def create_job(db: Session, request: JobCreateRequest) -> Tuple[GenerationJob, List[RecipientValidationFailure]]:
        """
        Validate incoming recipients, persist the Job and initial pending Certificate entities.
        """
        valid_recipients = []
        validation_failures: List[RecipientValidationFailure] = []

        # Validate recipient payload items
        for idx, rec in enumerate(request.recipients):
            try:
                name = rec.name.strip()
                if not name:
                    raise ValueError("Recipient name cannot be empty")
                valid_recipients.append((idx, rec))
            except Exception as e:
                validation_failures.append(
                    RecipientValidationFailure(
                        index=idx,
                        raw_data=rec.model_dump() if hasattr(rec, "model_dump") else dict(rec),
                        error=str(e),
                    )
                )

        total = len(request.recipients)
        valid_count = len(valid_recipients)
        invalid_count = len(validation_failures)

        # Generate human-friendly Job ID (e.g. JOB-1, JOB-2)
        job_id = JobService.generate_job_id(db)

        # Create GenerationJob row
        job = GenerationJob(
            id=job_id,
            title=request.title,
            description=request.description,
            issuer_name=request.issuer_name or settings.DEFAULT_ISSUER,
            signatory_name=request.signatory_name or "Authorized Director",
            signatory_title=request.signatory_title or settings.DEFAULT_SIGNATORY_TITLE,
            event_date=request.event_date or datetime.now(timezone.utc).strftime("%B %d, %Y"),
            status=JobStatus.PENDING,
            total_records=total,
            valid_records=valid_count,
            invalid_records=invalid_count,
            processed_records=0,
            successful_records=0,
            failed_records=invalid_count,
            error_summary=f"{invalid_count} records failed initial validation" if invalid_count > 0 else None,
        )
        db.add(job)
        db.flush()  # populate job.id

        # Create Certificate records for all valid recipients
        for _, rec in valid_recipients:
            cert = Certificate(
                job_id=job.id,
                recipient_name=rec.name,
                recipient_email=str(rec.email),
                extra_data=json.dumps(rec.extra_data) if rec.extra_data else None,
                status=CertificateStatus.PENDING,
            )
            db.add(cert)

        db.commit()
        db.refresh(job)
        return job, validation_failures

    @staticmethod
    def process_job(job_id: str, db: Optional[Session] = None, db_factory=None) -> None:
        """
        Background/Foreground processor for generating all certificates in a job.
        Provides strict error isolation: one recipient failure does not abort other generations.
        """
        close_db_after = False
        if db is None:
            factory = db_factory or SessionLocal
            db = factory()
            close_db_after = True

        try:
            job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            if not job:
                logger.error(f"Job '{job_id}' not found during execution.")
                return

            job.status = JobStatus.PROCESSING
            db.commit()

            pending_certs = db.query(Certificate).filter(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.PENDING
            ).all()

            for cert in pending_certs:
                cert.status = CertificateStatus.GENERATING
                db.commit()

                try:
                    # Parse extra data if present
                    extra = json.loads(cert.extra_data) if cert.extra_data else None

                    # Generate the PDF certificate
                    gen_result = CertificateGenerator.generate(
                        certificate_id=cert.id,
                        verification_code=cert.verification_code,
                        recipient_name=cert.recipient_name,
                        course_title=job.title,
                        issuer_name=job.issuer_name,
                        signatory_name=job.signatory_name,
                        signatory_title=job.signatory_title,
                        event_date=job.event_date,
                        extra_data=extra,
                    )

                    cert.file_path = gen_result["file_path"]
                    cert.file_name = gen_result["file_name"]
                    cert.file_size_bytes = gen_result["file_size_bytes"]
                    cert.status = CertificateStatus.SUCCESS
                    job.successful_records += 1

                except Exception as exc:
                    logger.exception(f"Error generating certificate {cert.id}: {exc}")
                    cert.status = CertificateStatus.FAILED
                    cert.error_message = str(exc)
                    job.failed_records += 1

                finally:
                    job.processed_records += 1
                    job.updated_at = datetime.now(timezone.utc)
                    db.commit()

            # Finalize Job status
            if job.total_records == 0 or (job.successful_records == job.total_records and job.failed_records == 0):
                job.status = JobStatus.COMPLETED
            elif job.successful_records > 0:
                job.status = JobStatus.PARTIALLY_COMPLETED
            else:
                job.status = JobStatus.FAILED

            job.completed_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            logger.critical(f"Critical unhandled error in job {job_id}: {e}", exc_info=True)
            if job:
                job.status = JobStatus.FAILED
                job.error_summary = f"Job processing aborted: {str(e)}"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            if close_db_after:
                db.close()

    @staticmethod
    def generate_job_id(db: Session) -> str:
        """Generate a sequential, human-friendly job identifier (e.g. JOB-1, JOB-2)."""
        import re
        existing_ids = db.query(GenerationJob.id).all()
        max_num = 0
        for (jid,) in existing_ids:
            if jid:
                match = re.search(r'(?:JOB-)?(\d+)$', str(jid).strip(), re.IGNORECASE)
                if match:
                    try:
                        num = int(match.group(1))
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
        next_num = max_num + 1 if max_num > 0 else 1
        return f"JOB-{next_num}"

    @staticmethod
    def get_job(db: Session, job_id: str) -> Optional[GenerationJob]:
        """Fetch job by ID with support for exact, case-insensitive, numeric, or prefix matching."""
        if not job_id:
            return None
        clean_id = str(job_id).strip()

        # 1. Exact match
        job = db.query(GenerationJob).filter(GenerationJob.id == clean_id).first()
        if job:
            return job

        # 2. Stripped leading '#' (e.g. '#JOB-1' -> 'JOB-1', '#1' -> '1')
        if clean_id.startswith("#"):
            stripped = clean_id.lstrip("#")
            job = db.query(GenerationJob).filter(GenerationJob.id == stripped).first()
            if job:
                return job
            if stripped.isdigit():
                job = db.query(GenerationJob).filter(GenerationJob.id == f"JOB-{stripped}").first()
                if job:
                    return job

        # 3. Numeric alias (e.g. '1' -> 'JOB-1')
        if clean_id.isdigit():
            job = db.query(GenerationJob).filter(GenerationJob.id == f"JOB-{clean_id}").first()
            if job:
                return job

        # 4. Case-insensitive match (e.g. 'job-1')
        job = db.query(GenerationJob).filter(GenerationJob.id.ilike(clean_id)).first()
        if job:
            return job

        # 5. Fallback: prefix match for legacy UUIDs
        return db.query(GenerationJob).filter(GenerationJob.id.startswith(clean_id)).first()

    @staticmethod
    def get_certificate(db: Session, certificate_id: str) -> Optional[Certificate]:
        """Fetch certificate by ID."""
        return db.query(Certificate).filter(Certificate.id == certificate_id).first()

    @staticmethod
    def get_certificate_by_code(db: Session, code: str) -> Optional[Certificate]:
        """Fetch certificate by unique verification code."""
        return db.query(Certificate).filter(Certificate.verification_code == code).first()

    @staticmethod
    def list_jobs(db: Session, skip: int = 0, limit: int = 50) -> Tuple[int, List[GenerationJob]]:
        """List generation jobs ordered newest first."""
        total = db.query(GenerationJob).count()
        jobs = db.query(GenerationJob).order_by(desc(GenerationJob.created_at)).offset(skip).limit(limit).all()
        return total, jobs

    @staticmethod
    def format_certificate_response(cert: Certificate, base_url: str = "") -> CertificateResponse:
        """Format Certificate ORM object into CertificateResponse schema."""
        download_url = None
        download_pdf_url = None
        download_png_url = None
        if cert.status == CertificateStatus.SUCCESS:
            download_url = f"{base_url}{settings.API_V1_PREFIX}/certificates/{cert.id}/download?format=pdf"
            download_pdf_url = f"{base_url}{settings.API_V1_PREFIX}/certificates/{cert.id}/download?format=pdf"
            download_png_url = f"{base_url}{settings.API_V1_PREFIX}/certificates/{cert.id}/download?format=png"

        return CertificateResponse(
            id=cert.id,
            job_id=cert.job_id,
            recipient_name=cert.recipient_name,
            recipient_email=cert.recipient_email,
            status=cert.status,
            verification_code=cert.verification_code,
            file_name=cert.file_name,
            file_size_bytes=cert.file_size_bytes,
            download_url=download_url,
            download_pdf_url=download_pdf_url,
            download_png_url=download_png_url,
            error_message=cert.error_message,
            created_at=cert.created_at,
            updated_at=cert.updated_at,
        )

    @classmethod
    def format_job_response(cls, job: GenerationJob, base_url: str = "") -> JobResponse:
        """Calculate progress percentage and URLs for JobResponse schema."""
        progress = 0.0
        if job.total_records > 0:
            progress = round((job.processed_records / job.total_records) * 100.0, 2)

        download_all_url = None
        download_all_pdf_url = None
        download_all_png_url = None
        if job.successful_records > 0:
            download_all_url = f"{base_url}{settings.API_V1_PREFIX}/jobs/{job.id}/download-all?format=pdf"
            download_all_pdf_url = f"{base_url}{settings.API_V1_PREFIX}/jobs/{job.id}/download-all?format=pdf"
            download_all_png_url = f"{base_url}{settings.API_V1_PREFIX}/jobs/{job.id}/download-all?format=png"

        return JobResponse(
            id=job.id,
            job_id=job.id,
            title=job.title,
            job_name=job.title,
            course_name=job.title,
            description=job.description,
            issuer_name=job.issuer_name,
            status=job.status,
            total_records=job.total_records,
            total_recipients=job.total_records,
            valid_records=job.valid_records,
            invalid_records=job.invalid_records,
            processed_records=job.processed_records,
            successful_records=job.successful_records,
            successful_count=job.successful_records,
            failed_records=job.failed_records,
            failed_count=job.failed_records,
            progress_percentage=progress,
            error_summary=job.error_summary,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            download_all_url=download_all_url,
            download_all_pdf_url=download_all_pdf_url,
            download_all_png_url=download_all_png_url,
        )

    @classmethod
    def format_job_detail_response(
        cls,
        job: GenerationJob,
        validation_failures: Optional[List[RecipientValidationFailure]] = None,
        base_url: str = "",
    ) -> JobDetailResponse:
        """Format detailed Job response with certificate items and failure reports."""
        base_resp = cls.format_job_response(job, base_url=base_url)
        certs = [cls.format_certificate_response(c, base_url=base_url) for c in (job.certificates or [])]

        return JobDetailResponse(
            **base_resp.model_dump(),
            certificates=certs,
            validation_failures=validation_failures or [],
        )

    @staticmethod
    def list_certificates(
        db: Session,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[int, List[Certificate]]:
        """List and filter certificates with search and pagination."""
        query = db.query(Certificate)

        if job_id and job_id.lower() != "all":
            resolved_job = JobService.get_job(db, job_id)
            if resolved_job:
                query = query.filter(Certificate.job_id == resolved_job.id)
            else:
                query = query.filter(Certificate.job_id == job_id)

        if status and status.upper() != "ALL":
            try:
                st_enum = CertificateStatus(status.upper())
                query = query.filter(Certificate.status == st_enum)
            except ValueError:
                pass

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.filter(
                (Certificate.recipient_name.ilike(search_pattern))
                | (Certificate.recipient_email.ilike(search_pattern))
                | (Certificate.verification_code.ilike(search_pattern))
                | (Certificate.course_name.ilike(search_pattern))
            )

        total = query.count()
        certs = query.order_by(desc(Certificate.created_at)).offset(skip).limit(limit).all()
        return total, certs

    @staticmethod
    def get_system_stats(db: Session) -> Dict[str, Any]:
        """Aggregate statistics for UI dashboard."""
        total_jobs = db.query(GenerationJob).count()
        total_certificates = db.query(Certificate).count()
        successful_certs = db.query(Certificate).filter(Certificate.status == CertificateStatus.SUCCESS).count()
        failed_certs = db.query(Certificate).filter(Certificate.status == CertificateStatus.FAILED).count()

        completed_jobs = db.query(GenerationJob).filter(GenerationJob.status == JobStatus.COMPLETED).count()
        partially_completed_jobs = db.query(GenerationJob).filter(GenerationJob.status == JobStatus.PARTIALLY_COMPLETED).count()
        processing_jobs = db.query(GenerationJob).filter(GenerationJob.status == JobStatus.PROCESSING).count()
        pending_jobs = db.query(GenerationJob).filter(GenerationJob.status == JobStatus.PENDING).count()
        failed_jobs = db.query(GenerationJob).filter(GenerationJob.status == JobStatus.FAILED).count()

        recent_jobs = db.query(GenerationJob).order_by(desc(GenerationJob.created_at)).limit(5).all()
        recent_activity = []
        for j in recent_jobs:
            display_id = f"#{j.id.replace('JOB-', '')}" if j.id.startswith("JOB-") else f"#{j.id}"
            recent_activity.append({
                "id": j.id,
                "title": f"Job {display_id} - {j.title}",
                "status": j.status.value,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "success": j.successful_records,
                "total": j.total_records,
            })

        return {
            "total_jobs": total_jobs,
            "total_certificates": total_certificates,
            "successful_certificates": successful_certs,
            "failed_certificates": failed_certs,
            "status_breakdown": {
                "completed": completed_jobs,
                "partially_completed": partially_completed_jobs,
                "processing": processing_jobs,
                "queued": pending_jobs,
                "failed": failed_jobs,
            },
            "recent_activity": recent_activity,
        }

    @classmethod
    def seed_test_scenarios(cls, db: Session, clear_existing: bool = False, base_url: str = "") -> List[JobResponse]:
        """
        Seed the 3 comprehensive test case scenarios:
        1. All Pass: 100% of recipient certificates generated successfully (COMPLETED).
        2. Some Failed: Partial failure demonstrating fault isolation (PARTIALLY_COMPLETED).
        3. All Failed: 100% failure demonstrating resilient batch-level error handling (FAILED).
        """
        from app.schemas.recipient import RecipientInput

        if clear_existing:
            db.query(Certificate).delete()
            db.query(GenerationJob).delete()
            db.commit()

        scenarios = [
            # Scenario 1: All Certificates Pass (100% Success)
            JobCreateRequest(
                title="Python Full Stack Bootcamp [TEST CASE: ALL PASS]",
                course_name="Python Full Stack Development",
                issuer_name="Global Tech Academy",
                signatory_name="Dr. Ramesh Mehta",
                signatory_title="Head of Curriculum",
                event_date="October 20, 2026",
                recipients=[
                    RecipientInput(name="Aarav Sharma", email="aarav.sharma@example.com", extra_data={"grade": "A+"}),
                    RecipientInput(name="Ananya Iyer", email="ananya.iyer@example.com", extra_data={"grade": "A", "honors": "Distinction"}),
                    RecipientInput(name="Rohan Verma", email="rohan.verma@example.com", extra_data={"grade": "A"}),
                    RecipientInput(name="Sneha Nair", email="sneha.nair@example.com", extra_data={"grade": "O", "honors": "First Class with Distinction"}),
                ],
            ),
            # Scenario 2: Some Certificates Fail (Fault Isolation)
            JobCreateRequest(
                title="Cloud & DevOps Masterclass [TEST CASE: SOME FAILED]",
                course_name="DevOps & Kubernetes Engineering",
                issuer_name="DevOps Certification Council",
                signatory_name="Pooja Deshmukh",
                signatory_title="Director of Cloud Certification",
                event_date="October 22, 2026",
                recipients=[
                    RecipientInput(name="Vikram Malhotra", email="vikram.m@example.com", extra_data={"grade": "A+"}),
                    RecipientInput(name="Meera Joshi", email="meera.j@example.com", extra_data={"grade": "B+"}),
                    RecipientInput(name="Kunal Singhania", email="kunal.s@example.com", extra_data={"grade": "A"}),
                    RecipientInput(
                        name="Corrupted Signature Student",
                        email="corrupted.cert@example.com",
                        extra_data={
                            "simulate_failure": True,
                            "failure_reason": "Digital signature verification failed: corrupted recipient signing key",
                        },
                    ),
                    RecipientInput(
                        name="Invalid Layout Record",
                        email="invalid.layout@example.com",
                        extra_data={
                            "simulate_failure": True,
                            "failure_reason": "Certificate template layout overflow: font metrics mismatch",
                        },
                    ),
                ],
            ),
            # Scenario 3: All Certificates Fail (Total Failure)
            JobCreateRequest(
                title="Cybersecurity Penetration Testing [TEST CASE: ALL FAILED]",
                course_name="Offensive Security & Pen-Testing",
                issuer_name="National Cybersecurity Institute",
                signatory_name="Col. Sunil Kapoor",
                signatory_title="Chief Security Officer",
                event_date="October 24, 2026",
                recipients=[
                    RecipientInput(
                        name="Audit Candidate Alpha",
                        email="candidate.alpha@example.com",
                        extra_data={
                            "simulate_failure": True,
                            "failure_reason": "Organization accreditation token expired on issuer authority",
                        },
                    ),
                    RecipientInput(
                        name="Audit Candidate Beta",
                        email="candidate.beta@example.com",
                        extra_data={
                            "simulate_failure": True,
                            "failure_reason": "Digital signature certificate authority unreachable (HTTP 503)",
                        },
                    ),
                    RecipientInput(
                        name="Audit Candidate Gamma",
                        email="candidate.gamma@example.com",
                        extra_data={
                            "simulate_failure": True,
                            "failure_reason": "Compliance verification policy rejected: security clearance mismatch",
                        },
                    ),
                ],
            ),
        ]

        created_jobs = []
        for req in scenarios:
            job, _ = cls.create_job(db=db, request=req)
            cls.process_job(job_id=job.id, db=db)
            refreshed = cls.get_job(db=db, job_id=job.id)
            created_jobs.append(cls.format_job_response(refreshed, base_url=base_url))

        return created_jobs
