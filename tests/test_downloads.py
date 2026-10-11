"""Automated tests for Certificate downloads, ZIP archiving, and verification."""
import io
import zipfile
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.services.certificate_generator import CertificateGenerator


def test_download_single_certificate_endpoint(client: TestClient):
    """Test downloading a generated certificate PDF via the download endpoint."""
    payload = {
        "job_name": "DevOps Masterclass",
        "recipients": [{"name": "Sara Connor", "email": "sara@example.com"}],
    }
    job_res = client.post("/api/v1/certificate-jobs?sync=true", json=payload)
    cert_id = job_res.json()["certificates"][0]["id"]

    # Download single certificate PDF
    res = client.get(f"/api/v1/certificates/{cert_id}/download")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF")


def test_retrieve_non_existent_certificate_returns_404(client: TestClient):
    """Test downloading non-existent certificate returns 404."""
    response = client.get("/api/v1/certificates/00000000-0000-0000-0000-000000000000/download")
    assert response.status_code == 404


def test_download_all_zip_archive(client: TestClient):
    """Test bundling and downloading all certificates in a job as a ZIP archive."""
    payload = {
        "job_name": "Kubernetes Certification",
        "recipients": [
            {"name": "User One", "email": "user1@example.com"},
            {"name": "User Two", "email": "user2@example.com"},
        ],
    }
    job_res = client.post("/api/v1/certificate-jobs?sync=true", json=payload)
    job_id = job_res.json()["id"]

    # Download ZIP bundle
    zip_res = client.get(f"/api/v1/jobs/{job_id}/download-all")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"

    # Verify ZIP file format
    zf = zipfile.ZipFile(io.BytesIO(zip_res.content))
    assert len(zf.namelist()) == 2
    for fname in zf.namelist():
        assert fname.endswith(".pdf")


def test_download_all_with_no_success_returns_400(client: TestClient):
    """Test download-all returns 400 if no successful certificates exist."""
    def mock_fail(*args, **kwargs):
        raise RuntimeError("Fail generation")

    with patch.object(CertificateGenerator, "generate", side_effect=mock_fail):
        job_res = client.post(
            "/api/v1/jobs?sync=true",
            json={"title": "Failed Job", "recipients": [{"name": "A", "email": "a@example.com"}]},
        )
        job_id = job_res.json()["id"]

        zip_res = client.get(f"/api/v1/jobs/{job_id}/download-all")
        assert zip_res.status_code == 400


def test_public_certificate_verification(client: TestClient):
    """Test verifying a valid certificate and an invalid certificate code."""
    payload = {
        "job_name": "Cybersecurity Fundamentals",
        "recipients": [{"name": "Alex Mercer", "email": "alex@example.com"}],
    }
    job_res = client.post("/api/v1/certificate-jobs?sync=true", json=payload)
    cert = job_res.json()["certificates"][0]
    ver_code = cert["verification_code"]

    # Valid code
    verify_res = client.get(f"/api/v1/certificates/verify/{ver_code}")
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True
    assert verify_res.json()["recipient_name"] == "Alex Mercer"

    # Invalid code
    bad_res = client.get("/api/v1/certificates/verify/CERT-INVALID999")
    assert bad_res.status_code == 200
    assert bad_res.json()["valid"] is False


def test_dashboard_ui_endpoint(client: TestClient):
    """Test that the UI dashboard HTML page is served correctly."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Bulk Certificate" in res.text


def test_health_and_root_endpoints(client: TestClient):
    """Test root and health check endpoints."""
    root_res = client.get("/")
    assert root_res.status_code == 200
    assert "docs_url" in root_res.json()

    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"


def test_download_certificate_png_and_pdf_format_options(client: TestClient):
    """Test downloading certificate with format=pdf and format=png options."""
    payload = {
        "job_name": "Full Stack Web Bootcamp",
        "recipients": [{"name": "Priya Patel", "email": "priya@example.com"}],
    }
    job_res = client.post("/api/v1/certificate-jobs?sync=true", json=payload)
    cert_id = job_res.json()["certificates"][0]["id"]

    # 1. Download as PDF via query param
    pdf_res = client.get(f"/api/v1/certificates/{cert_id}/download?format=pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF")

    # 2. Download as PNG via query param
    png_res = client.get(f"/api/v1/certificates/{cert_id}/download?format=png")
    assert png_res.status_code == 200
    assert png_res.headers["content-type"] == "image/png"
    assert png_res.content.startswith(b"\x89PNG\r\n\x1a\n")

    # 3. Direct /download/png endpoint
    direct_png = client.get(f"/api/v1/certificates/{cert_id}/download/png")
    assert direct_png.status_code == 200
    assert direct_png.headers["content-type"] == "image/png"
    assert direct_png.content.startswith(b"\x89PNG\r\n\x1a\n")

    # 4. Direct /download/pdf endpoint
    direct_pdf = client.get(f"/api/v1/certificates/{cert_id}/download/pdf")
    assert direct_pdf.status_code == 200
    assert direct_pdf.headers["content-type"] == "application/pdf"
    assert direct_pdf.content.startswith(b"%PDF")


def test_download_all_zip_archive_in_png_format(client: TestClient):
    """Test downloading bulk certificates ZIP archive containing PNG images."""
    payload = {
        "job_name": "Cloud Native Architecture",
        "recipients": [
            {"name": "Dev User 1", "email": "dev1@example.com"},
            {"name": "Dev User 2", "email": "dev2@example.com"},
        ],
    }
    job_res = client.post("/api/v1/certificate-jobs?sync=true", json=payload)
    job_id = job_res.json()["id"]

    # Download PNG ZIP bundle
    zip_res = client.get(f"/api/v1/jobs/{job_id}/download-all?format=png")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"

    # Verify all files inside ZIP are PNG images
    zf = zipfile.ZipFile(io.BytesIO(zip_res.content))
    assert len(zf.namelist()) == 2
    for fname in zf.namelist():
        assert fname.endswith(".png")
