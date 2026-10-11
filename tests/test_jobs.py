"""Automated tests for Job creation, input validation, status tracking, and fault isolation."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.services.certificate_generator import CertificateGenerator


# -------------------------------------------------------------
# 1. Job Creation Tests
# -------------------------------------------------------------

def test_create_generation_job_bulk(client: TestClient):
    """Test creating a bulk certificate generation job with valid recipients."""
    payload = {
        "title": "FastAPI & Microservices Masterclass",
        "description": "Completed 40 hours of advanced backend architecture",
        "issuer_name": "Antigravity Engineering Academy",
        "signatory_name": "Dr. Sarah Mitchell",
        "signatory_title": "Head of Learning",
        "event_date": "October 24, 2026",
        "recipients": [
            {"name": "Alice Johnson", "email": "alice@example.com", "extra_data": {"grade": "A+"}},
            {"name": "Bob Smith", "email": "bob@example.com", "extra_data": {"honors": "Distinction"}},
            {"name": "Charlie Brown", "email": "charlie@example.com"},
        ],
    }

    response = client.post("/api/v1/jobs?sync=true", json=payload)
    assert response.status_code in (200, 202)

    data = response.json()
    assert "id" in data
    assert data["title"] == "FastAPI & Microservices Masterclass"
    assert data["total_records"] == 3
    assert data["valid_records"] == 3
    assert data["invalid_records"] == 0
    assert data["successful_records"] == 3
    assert data["status"] == "COMPLETED"
    assert len(data["certificates"]) == 3

    for cert in data["certificates"]:
        assert cert["status"] == "SUCCESS"
        assert cert["download_url"] is not None
        assert cert["verification_code"].startswith("CERT-")


def test_create_generation_job_defaults(client: TestClient):
    """Test creating a job using default issuer and date settings."""
    payload = {
        "title": "Machine Learning Bootcamp",
        "recipients": [
            {"name": "Jane Doe", "email": "jane@example.com"}
        ],
    }

    response = client.post("/api/v1/jobs?sync=true", json=payload)
    assert response.status_code in (200, 202)

    data = response.json()
    assert data["issuer_name"] == "Global Certification Authority"
    assert data["total_records"] == 1
    assert data["status"] == "COMPLETED"


def test_create_generation_job_async_background(client: TestClient):
    """Test submitting a job with default async background processing."""
    payload = {
        "title": "Async Processing Deep Dive",
        "recipients": [
            {"name": "Async Developer", "email": "async@example.com"}
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["id"] is not None
    assert data["total_records"] == 1


# -------------------------------------------------------------
# 2. Input Validation Tests
# -------------------------------------------------------------

def test_validation_empty_recipients_list(client: TestClient):
    """Test validation fails when recipients list is empty."""
    payload = {
        "title": "Cloud Architecture",
        "recipients": [],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_missing_title(client: TestClient):
    """Test validation fails when title is missing."""
    payload = {
        "recipients": [
            {"name": "Alice", "email": "alice@example.com"}
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_empty_title_whitespace(client: TestClient):
    """Test validation fails when title is only whitespace."""
    payload = {
        "title": "   ",
        "recipients": [
            {"name": "Alice", "email": "alice@example.com"}
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_invalid_email_format(client: TestClient):
    """Test validation fails when recipient email is malformed."""
    payload = {
        "title": "Docker Essentials",
        "recipients": [
            {"name": "John Doe", "email": "not-a-valid-email"}
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_empty_recipient_name(client: TestClient):
    """Test validation fails when recipient name is empty."""
    payload = {
        "title": "DevOps Intensive",
        "recipients": [
            {"name": "   ", "email": "valid@example.com"}
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


# -------------------------------------------------------------
# 3. Fault Isolation & Failure Handling Tests
# -------------------------------------------------------------

def test_individual_certificate_failure_isolation(client: TestClient):
    """
    Test that an unexpected generation failure on one recipient does NOT
    prevent other certificates in the batch from successfully generating.
    """
    original_generate = CertificateGenerator.generate

    def mock_generate_with_single_failure(*args, **kwargs):
        recipient_name = kwargs.get("recipient_name")
        if recipient_name == "Faulty User":
            raise RuntimeError("Simulated render engine crash for Faulty User")
        return original_generate(*args, **kwargs)

    payload = {
        "title": "Robustness & Fault Tolerance Course",
        "recipients": [
            {"name": "Valid Recipient One", "email": "valid1@example.com"},
            {"name": "Faulty User", "email": "faulty@example.com"},
            {"name": "Valid Recipient Two", "email": "valid2@example.com"},
        ],
    }

    with patch.object(CertificateGenerator, "generate", side_effect=mock_generate_with_single_failure):
        response = client.post("/api/v1/jobs?sync=true", json=payload)
        assert response.status_code in (200, 202)
        data = response.json()

        assert data["status"] == "PARTIALLY_COMPLETED"
        assert data["total_records"] == 3
        assert data["processed_records"] == 3
        assert data["successful_records"] == 2
        assert data["failed_records"] == 1

        certs = {c["recipient_name"]: c for c in data["certificates"]}
        assert certs["Valid Recipient One"]["status"] == "SUCCESS"
        assert certs["Valid Recipient Two"]["status"] == "SUCCESS"
        assert certs["Faulty User"]["status"] == "FAILED"
        assert "Simulated render engine crash" in certs["Faulty User"]["error_message"]


def test_five_recipients_one_deliberate_failure_per_spec(client: TestClient):
    """
    Explicit test required by assignment specification (Page 6):
    'Test five recipients where one generation deliberately raises an exception.
    The expected final result is four successful certificates and one failed certificate,
    with the job summary matching the individual records.'
    """
    original_generate = CertificateGenerator.generate

    def mock_generate_five(*args, **kwargs):
        recipient_name = kwargs.get("recipient_name")
        if recipient_name == "Recipient 3 (Crash)":
            raise RuntimeError("Deliberate rendering failure for recipient 3")
        return original_generate(*args, **kwargs)

    payload = {
        "job_name": "Python Backend Mastery",
        "recipients": [
            {"name": "Recipient 1", "email": "r1@example.com"},
            {"name": "Recipient 2", "email": "r2@example.com"},
            {"name": "Recipient 3 (Crash)", "email": "r3@example.com"},
            {"name": "Recipient 4", "email": "r4@example.com"},
            {"name": "Recipient 5", "email": "r5@example.com"},
        ],
    }

    with patch.object(CertificateGenerator, "generate", side_effect=mock_generate_five):
        response = client.post("/api/v1/certificate-jobs?sync=true", json=payload)
        assert response.status_code in (200, 202)
        data = response.json()

        assert data["status"] == "PARTIALLY_COMPLETED"
        assert data["total_records"] == 5
        assert data["total_recipients"] == 5
        assert data["successful_records"] == 4
        assert data["successful_count"] == 4
        assert data["failed_records"] == 1
        assert data["failed_count"] == 1

        # Check job summary matches individual records
        certs = data["certificates"]
        success_certs = [c for c in certs if c["status"] == "SUCCESS"]
        failed_certs = [c for c in certs if c["status"] == "FAILED"]
        assert len(success_certs) == 4
        assert len(failed_certs) == 1
        assert "Deliberate rendering failure" in failed_certs[0]["error_message"]



def test_all_certificates_failing_sets_job_failed(client: TestClient):
    """Test that if all certificate generations fail, job status is FAILED."""
    def mock_fail_all(*args, **kwargs):
        raise RuntimeError("Complete generator outage")

    payload = {
        "title": "Outage Test Course",
        "recipients": [
            {"name": "User One", "email": "u1@example.com"},
            {"name": "User Two", "email": "u2@example.com"},
        ],
    }

    with patch.object(CertificateGenerator, "generate", side_effect=mock_fail_all):
        response = client.post("/api/v1/jobs?sync=true", json=payload)
        data = response.json()
        assert data["status"] == "FAILED"
        assert data["successful_records"] == 0
        assert data["failed_records"] == 2


# -------------------------------------------------------------
# 4. Status Tracking & Assignment PDF Spec Endpoint Tests
# -------------------------------------------------------------

def test_get_job_status_and_progress(client: TestClient):
    """Test retrieving job status, statistics, and certificate lists."""
    payload = {
        "title": "Full Stack Mastery",
        "recipients": [
            {"name": "Developer One", "email": "dev1@example.com"},
            {"name": "Developer Two", "email": "dev2@example.com"},
        ],
    }

    create_res = client.post("/api/v1/jobs?sync=true", json=payload)
    job_id = create_res.json()["id"]

    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == 200

    data = status_res.json()
    assert data["id"] == job_id
    assert data["status"] == "COMPLETED"
    assert data["total_records"] == 2
    assert data["processed_records"] == 2
    assert data["successful_records"] == 2
    assert data["failed_records"] == 0
    assert data["progress_percentage"] == 100.0


def test_get_non_existent_job_returns_404(client: TestClient):
    """Test requesting status of non-existent job returns 404."""
    response = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_list_jobs_pagination(client: TestClient):
    """Test listing jobs with pagination."""
    for i in range(2):
        client.post(
            "/api/v1/jobs?sync=true",
            json={
                "title": f"Workshop #{i + 1}",
                "recipients": [{"name": f"User {i}", "email": f"user{i}@example.com"}],
            },
        )

    list_res = client.get("/api/v1/jobs?limit=2&skip=0")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] >= 2


def test_pdf_spec_certificate_jobs_endpoint(client: TestClient):
    """
    Test POST /api/v1/certificate-jobs using the exact payload structure
    specified in section 4 of the assignment PDF:
    {
        "job_name": "Python Training Program",
        "course_name": "Python Programming",
        "completion_date": "2026-10-10",
        "recipients": [ ... ]
    }
    """
    payload = {
        "job_name": "Python Training Program",
        "course_name": "Python Programming",
        "completion_date": "2026-10-10",
        "recipients": [
            {"name": "Rahul Sharma", "email": "rahul@example.com"},
            {"name": "Priya Verma", "email": "priya@example.com"},
        ],
    }

    response = client.post("/api/v1/certificate-jobs?sync=true", json=payload)
    assert response.status_code in (200, 202)
    data = response.json()

    assert data["job_name"] == "Python Training Program"
    assert data["total_recipients"] == 2
    assert data["successful_count"] == 2
    assert data["status"] == "COMPLETED"

    job_id = data["id"]

    # Test GET /api/v1/certificate-jobs/{job_id}/certificates
    certs_res = client.get(f"/api/v1/certificate-jobs/{job_id}/certificates")
    assert certs_res.status_code == 200
    certs_data = certs_res.json()
    assert len(certs_data) == 2


# -------------------------------------------------------------
# 5. Dedicated Test Scenarios (All Pass, Some Failed, All Failed)
# -------------------------------------------------------------

def test_job_scenario_all_certificates_pass(client: TestClient):
    """Test Case Scenario 1: 100% of recipient certificates pass and job is COMPLETED."""
    payload = {
        "title": "Machine Learning Specialization [Scenario: All Pass]",
        "course_name": "Deep Learning & Neural Networks",
        "recipients": [
            {"name": "Alice Cooper", "email": "alice@example.com"},
            {"name": "Bob Dylan", "email": "bob@example.com", "extra_data": {"grade": "A+"}},
            {"name": "Charlie Brown", "email": "charlie@example.com"},
        ],
    }

    res = client.post("/api/v1/jobs?sync=true", json=payload)
    assert res.status_code in (200, 202)
    data = res.json()

    assert data["status"] == "COMPLETED"
    assert data["total_records"] == 3
    assert data["successful_records"] == 3
    assert data["failed_records"] == 0
    assert data["progress_percentage"] == 100.0

    # Verify each certificate has SUCCESS status and download URLs
    job_id = data["id"]
    certs_res = client.get(f"/api/v1/jobs/{job_id}/certificates")
    assert certs_res.status_code == 200
    for cert in certs_res.json():
        assert cert["status"] == "SUCCESS"
        assert cert["download_url"] is not None
        assert cert["download_pdf_url"] is not None
        assert cert["download_png_url"] is not None


def test_job_scenario_some_certificates_failed_partial_completed(client: TestClient):
    """Test Case Scenario 2: Some certificates fail while others pass, demonstrating fault isolation (PARTIALLY_COMPLETED)."""
    payload = {
        "title": "Cloud Architect Bootcamp [Scenario: Some Failed]",
        "course_name": "AWS & Multi-Cloud Architecture",
        "recipients": [
            {"name": "Pass Candidate 1", "email": "pass1@example.com"},
            {"name": "Pass Candidate 2", "email": "pass2@example.com"},
            {
                "name": "Fail Candidate 1",
                "email": "fail1@example.com",
                "extra_data": {
                    "simulate_failure": True,
                    "failure_reason": "Digital signature verification failed: corrupted recipient signing key",
                },
            },
            {
                "name": "Fail Candidate 2",
                "email": "fail2@example.com",
                "extra_data": {
                    "simulate_failure": True,
                    "failure_reason": "Certificate template layout overflow: font metrics mismatch",
                },
            },
        ],
    }

    res = client.post("/api/v1/jobs?sync=true", json=payload)
    assert res.status_code in (200, 202)
    data = res.json()

    assert data["status"] == "PARTIALLY_COMPLETED"
    assert data["total_records"] == 4
    assert data["successful_records"] == 2
    assert data["failed_records"] == 2
    assert data["progress_percentage"] == 100.0

    # Verify individual recipient fault isolation
    job_id = data["id"]
    certs_res = client.get(f"/api/v1/jobs/{job_id}/certificates")
    assert certs_res.status_code == 200
    certs = certs_res.json()

    pass_certs = [c for c in certs if c["status"] == "SUCCESS"]
    fail_certs = [c for c in certs if c["status"] == "FAILED"]

    assert len(pass_certs) == 2
    assert len(fail_certs) == 2

    for c in pass_certs:
        assert c["download_url"] is not None
    for c in fail_certs:
        assert c["download_url"] is None
        assert c["error_message"] is not None
        assert len(c["error_message"]) > 0


def test_job_scenario_all_certificates_failed(client: TestClient):
    """Test Case Scenario 3: All certificates fail, job transitions cleanly to FAILED."""
    payload = {
        "title": "Critical Compliance Audit [Scenario: All Failed]",
        "course_name": "Enterprise Security Audit",
        "recipients": [
            {
                "name": "Audit Target 1",
                "email": "audit1@example.com",
                "extra_data": {
                    "simulate_failure": True,
                    "failure_reason": "Organization accreditation token expired on issuer authority",
                },
            },
            {
                "name": "Audit Target 2",
                "email": "audit2@example.com",
                "extra_data": {
                    "simulate_failure": True,
                    "failure_reason": "Digital signature certificate authority unreachable (HTTP 503)",
                },
            },
        ],
    }

    res = client.post("/api/v1/jobs?sync=true", json=payload)
    assert res.status_code in (200, 202)
    data = res.json()

    assert data["status"] == "FAILED"
    assert data["total_records"] == 2
    assert data["successful_records"] == 0
    assert data["failed_records"] == 2
    assert data["progress_percentage"] == 100.0


def test_seed_test_scenarios_api_endpoint(client: TestClient):
    """Test the POST /api/v1/jobs/seed-test-scenarios endpoint generating all 3 scenario jobs."""
    res = client.post("/api/v1/jobs/seed-test-scenarios?clear_existing=true")
    assert res.status_code == 200
    jobs = res.json()

    assert len(jobs) == 3
    statuses = [j["status"] for j in jobs]
    assert "COMPLETED" in statuses
    assert "PARTIALLY_COMPLETED" in statuses
    assert "FAILED" in statuses
