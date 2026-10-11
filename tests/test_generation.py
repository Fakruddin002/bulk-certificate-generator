"""Automated tests for ReportLab PDF certificate generation and rendering."""
import os
import pytest
from app.services.certificate_generator import CertificateGenerator


def test_certificate_pdf_generation_direct(tmp_path):
    """Test generating a single certificate PDF and verifying its existence and headers."""
    result = CertificateGenerator.generate(
        certificate_id="test-gen-001",
        verification_code="CERT-TESTGEN1",
        recipient_name="John Doe",
        course_title="Advanced Python Programming",
        issuer_name="Global Certification Authority",
        signatory_name="Director Test",
        signatory_title="Authorized Signatory",
        event_date="October 20, 2026",
        output_dir=tmp_path,
    )

    assert result is not None
    assert "file_path" in result
    assert "verification_url" in result
    assert os.path.exists(result["file_path"])
    assert result["file_size_bytes"] > 1000

    # Verify PDF signature bytes
    with open(result["file_path"], "rb") as f:
        header = f.read(4)
        assert header == b"%PDF"


def test_certificate_with_extra_metadata(tmp_path):
    """Test generating a certificate with extra metadata such as grade and honors."""
    result = CertificateGenerator.generate(
        certificate_id="test-gen-002",
        verification_code="CERT-TESTGEN2",
        recipient_name="Jane Smith",
        course_title="Machine Learning Engineering",
        issuer_name="Global Certification Authority",
        extra_data={"grade": "A+", "honors": "Distinction"},
        output_dir=tmp_path,
    )

    assert os.path.exists(result["file_path"])
    assert result["file_size_bytes"] > 1000
