import os
import zipfile
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from app.config import settings
from app.models.certificate_record import CertificateRecord
from app.services.certificate_generator import CertificateGenerator

logger = logging.getLogger(__name__)


class StorageService:
    """Service handling certificate file storage, retrieval, and ZIP bundle creation for PDF and PNG."""

    @classmethod
    def ensure_png_file(cls, pdf_path: str) -> str:
        """Ensure high-resolution PNG version of certificate exists, creating if missing."""
        png_path = Path(pdf_path).with_suffix(".png")
        if not png_path.exists():
            if not os.path.exists(pdf_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Source PDF certificate not found to render PNG",
                )
            try:
                CertificateGenerator.render_pdf_to_png(pdf_path, png_path=png_path, scale=2.0)
            except Exception as e:
                logger.error(f"Failed to render PNG for {pdf_path}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate PNG certificate: {str(e)}",
                )
        return str(png_path)

    @classmethod
    def get_certificate_file_response(cls, cert: CertificateRecord, format: str = "pdf") -> FileResponse:
        """Return a FileResponse for downloading an individual certificate in PDF or PNG format."""
        format_lower = (format or "pdf").lower().strip()
        if format_lower not in ["pdf", "png"]:
            format_lower = "pdf"

        file_path = cert.file_path
        if not file_path or not os.path.exists(file_path):
            # Check default certificates directory as fallback
            fallback = os.path.join(settings.CERTIFICATES_DIR, cert.file_name or f"{cert.id}.pdf")
            if os.path.exists(fallback):
                file_path = fallback
            else:
                logger.error(f"Certificate file not found: {file_path}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Certificate file not found on disk",
                )

        clean_recipient = cert.recipient_name.replace(" ", "_")

        if format_lower == "png":
            png_path = cls.ensure_png_file(file_path)
            download_name = f"Certificate_{clean_recipient}.png"
            return FileResponse(
                path=png_path,
                filename=download_name,
                media_type="image/png",
                headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
            )
        else:
            download_name = cert.file_name or f"Certificate_{clean_recipient}.pdf"
            return FileResponse(
                path=file_path,
                filename=download_name,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
            )

    @classmethod
    def create_job_zip_archive(
        cls,
        job_id: str,
        certificates: List[CertificateRecord],
        format: str = "pdf",
    ) -> str:
        """
        Create a ZIP archive containing certificates for a job in PDF, PNG, or both formats.
        Returns the path to the generated ZIP archive.
        """
        if not certificates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No successful certificates available to bundle for this job",
            )

        format_lower = (format or "pdf").lower().strip()
        if format_lower not in ["pdf", "png", "all", "both"]:
            format_lower = "pdf"

        os.makedirs(settings.CERTIFICATES_DIR, exist_ok=True)
        zip_filename = f"job_{job_id}_certificates_{format_lower}.zip"
        zip_path = os.path.join(settings.CERTIFICATES_DIR, zip_filename)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for cert in certificates:
                pdf_path = cert.file_path
                if not pdf_path or not os.path.exists(pdf_path):
                    fallback = os.path.join(settings.CERTIFICATES_DIR, cert.file_name or f"{cert.id}.pdf")
                    if os.path.exists(fallback):
                        pdf_path = fallback
                    else:
                        continue

                clean_name = cert.recipient_name.replace(" ", "_")
                cert_code = cert.verification_code or cert.id[:8]

                if format_lower in ["pdf", "all", "both"]:
                    pdf_arcname = f"Certificate_{clean_name}_{cert_code}.pdf"
                    zip_file.write(pdf_path, arcname=pdf_arcname)

                if format_lower in ["png", "all", "both"]:
                    try:
                        png_path = cls.ensure_png_file(pdf_path)
                        png_arcname = f"Certificate_{clean_name}_{cert_code}.png"
                        zip_file.write(png_path, arcname=png_arcname)
                    except Exception as err:
                        logger.warning(f"Could not include PNG for {cert.id} in ZIP: {err}")

        return zip_path
