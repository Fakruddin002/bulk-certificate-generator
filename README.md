# Bulk Certificate Generator API

A high-performance, fault-tolerant backend system for bulk certificate generation, progress tracking, and verification built with **FastAPI**, **SQLAlchemy**, and **ReportLab**.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Key Architectural & Design Decisions](#key-architectural--design-decisions)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Setup & Installation](#setup--installation)
6. [Relational Database Setup, Storage & Retrieval](#relational-database-setup-storage--retrieval)
7. [Running the Application](#running-the-application)
8. [How to Submit a Certificate Generation Request](#how-to-submit-a-certificate-generation-request)
   - [Method 1: Interactive Web Dashboard (UI)](#method-1-interactive-web-dashboard-ui)
   - [Method 2: Programmatic REST API (cURL / HTTP)](#method-2-programmatic-rest-api-curl--http)
9. [Tracking Status & Retrieving Generated Certificates](#tracking-status--retrieving-generated-certificates)
10. [Comprehensive Test Cases & Scenarios (All Pass, Some Failed, All Failed)](#comprehensive-test-cases--scenarios-all-pass-some-failed-all-failed)
11. [Running Automated Tests](#running-automated-tests)
12. [Interactive UI Dashboards Overview](#interactive-ui-dashboards-overview)
13. [10 Critical Interview & Design Questions (Answered)](#10-critical-interview--design-questions-answered)


---

## Project Overview

Organizations regularly host webinars, hackathons, academic courses, and corporate training programs. Once an event concludes, hundreds or thousands of participants require personalized certificates.

This backend provides:
* **Bulk Processing**: Ingest hundreds or thousands of recipients in a single API payload.
* **Fault Isolation**: A failure or corrupted record for one recipient does **not** halt or cancel the generation of other valid recipients in the batch.
* **Real-time Status & Progress Tracking**: Clients can poll job progress (`PENDING` -> `PROCESSING` -> `COMPLETED` / `PARTIALLY_COMPLETED` / `FAILED`), with processed, successful, and failed counts.
* **Professional PDF Generation**: Generates print-ready vector PDF certificates with ornamental borders, elegant typography, and a dynamic verification QR code.
* **Single & Batch Retrieval**: Individual PDF downloads and one-click ZIP archive downloads for entire batches.
* **Public Verification Endpoint**: Real-time authenticity verification via unique cryptographic certificate codes and QR code scans.

---

## Key Architectural & Design Decisions

### 1. Asynchronous vs. Synchronous Processing
* **Default Mode (Asynchronous via Background Tasks)**:
  - Certificate generation involves graphic rendering and file system I/O write operations. Generating hundreds of PDFs in a single HTTP request would block the server thread and trigger client/gateway timeouts (HTTP 504).
  - The API immediately validates incoming data, persists initial job and certificate records in the database, and returns `HTTP 202 Accepted` along with the `job_id`.
  - Generation is offloaded to background task execution (`fastapi.BackgroundTasks`), allowing non-blocking responsiveness.
* **Synchronous Option (`?sync=true`)**:
  - The endpoint supports `POST /api/v1/jobs?sync=true` or `POST /api/v1/certificate-jobs?sync=true` for instant execution when integrating with automated test suites or small batches.

### 2. Strict Input Validation & Fault Tolerance
* **Validation Layer**: Handled via Pydantic v2 schemas (`EmailStr`, trimmed strings, non-empty bounds).
* **Isolation of Failures**:
  - Every recipient is processed inside an independent `try/except` boundary.
  - If a certificate fails during PDF rendering (e.g. character encoding issue or render error), the exception is captured per item.
  - The affected certificate is marked as `FAILED` with a descriptive `error_message`.
  - The remaining certificates continue processing uninterrupted.
  - The overall job status transitions to `PARTIALLY_COMPLETED` (or `COMPLETED` if all succeed).

### 3. PDF Certificate Rendering Engine
* **ReportLab**: Chosen for pure-Python performance, vector-based PDF fidelity, and exact coordinate typography.
* Each certificate embeds:
  - Issuer name & organization branding
  - Recipient's full name (prominently styled)
  - Course / Event title & optional honors/grade metadata
  - Date of issuance and signature block
  - **Dynamic QR Code** pointing to `/api/v1/certificates/verify/{verification_code}`

### 4. Database Architecture
Two main tables maintain complete isolation between batch requests and recipient-level records:
- **`generation_jobs`**: Stores high-level job metadata, overall status, total/successful/failed counts, and timestamps.
- **`certificates` (alias `certificate_records`)**: Stores recipient details, status, file path, error message, and unique verification code, linked to `generation_jobs` via foreign key with cascade deletion.

---

## Technology Stack

* **Language**: Python 3.10+ (Tested on Python 3.13)
* **API Framework**: FastAPI (Async ASGI, OpenAPI documentation)
* **ORM & Database**: SQLAlchemy 2.0 (SQLite for zero-config local development, MySQL/PostgreSQL compatible via PyMySQL)
* **Data Validation**: Pydantic v2 & `email-validator`
* **PDF Rendering**: ReportLab & Pillow
* **QR Code Engine**: `qrcode`
* **Testing**: Pytest, Pytest-Asyncio, HTTPX
* **Server**: Uvicorn ASGI Server

---

## Project Structure

```text
bulk-certificate-generator/
├── .venv/                              # Python 3.13 virtual environment
├── .vscode/
│   └── settings.json                   # Python interpreter configuration
├── alembic/                            # Database schema migrations
│   ├── env.py
│   └── script.py.mako
├── alembic.ini                         # Alembic migration configuration
├── app/                                # Main FastAPI Application Source Code
│   ├── core/
│   │   └── config.py                   # Application settings & environment variables
│   ├── models/                         # SQLAlchemy Database Models
│   │   ├── generation_job.py           # GenerationJob model & JobStatus enum
│   │   ├── certificate_record.py       # Certificate/CertificateRecord model & status enum
│   │   ├── job.py                      # Re-exports for jobs
│   │   └── certificate.py              # Re-exports for certificates
│   ├── schemas/                        # Pydantic Validation Schemas
│   │   ├── recipient.py                # Recipient input parsing & validation
│   │   ├── job.py                      # Job request & status response schemas
│   │   └── certificate.py              # Certificate response schemas
│   ├── services/                       # Business Logic Layer
│   │   ├── certificate_generator.py    # ReportLab PDF rendering & vector layout
│   │   ├── job_processor.py            # Async batch certificate generation processor
│   │   ├── job_service.py              # Job state management & DB queries
│   │   └── storage_service.py          # PDF storage, file paths & ZIP archives
│   ├── routers/                        # API Endpoints (Controllers)
│   │   ├── jobs.py                     # /api/v1/certificate-jobs & /api/v1/jobs
│   │   └── certificates.py             # /api/v1/certificates (Verify & Download)
│   ├── static/                         # Web UI Dashboard (Frontend)
│   │   ├── css/                        # UI styling
│   │   ├── js/                         # Frontend logic & API polling
│   │   └── index.html                  # 4-Screen Dashboard
│   ├── database.py                     # Database engine & sessionmaker
│   └── main.py                         # FastAPI entry point, lifespan, CORS & routers
├── generated_certificates/             # Output folder for generated PDFs
├── storage/
│   └── archives/                       # Output folder for batch ZIP archives
├── templates/
│   └── certificate_template.png        # Background image template for certificates
├── tests/                              # Pytest automated test suite
│   ├── conftest.py                     # Test client fixtures & database setups
│   ├── test_jobs.py                    # Tests for job creation, validation & fault tolerance
│   ├── test_generation.py              # Tests for PDF rendering engine
│   └── test_downloads.py               # Tests for PDF & ZIP download endpoints
├── certificates.db                     # SQLite database file
├── requirements.txt                    # Project dependencies
└── README.md                           # Documentation & API specs
```

---

## Setup & Installation

### Prerequisites
* Python 3.10 or higher (Python 3.13 recommended)
* Git

### Step-by-Step Installation

1. **Clone or navigate to the repository**:
   ```bash
   cd d:/bulk-certificate-generator
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install project dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   The application works out-of-the-box with SQLite (`certificates.db`). To customize settings or switch to MySQL, create a `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```
   For MySQL:
   ```env
   DATABASE_URL="mysql+pymysql://username:password@localhost:3306/certificates_db"
   ```

---

## Relational Database Setup, Storage & Retrieval

### 1. Is SQLite a Relational Database?
**Yes.** SQLite is a full-featured, ACID-compliant **Relational Database Management System (RDBMS)**. It implements SQL standards, structured tables, columns, constraints, foreign key cascades, and transactional integrity.
- The `.db` file (e.g. `certificates.db` in your root folder) is the physical, self-contained disk file storing the database tables and records.
- Zero external server setup is required, making it lightweight for local development and CI/CD testing.

### 2. Where is the Database Configured?
The database connection string is defined in [app/config.py](file:///d:/bulk-certificate-generator/app/config.py) via Pydantic Settings and loaded into [app/database.py](file:///d:/bulk-certificate-generator/app/database.py):

```python
# Default setting in app/config.py
DATABASE_URL: str = "sqlite:///./certificates.db"
```

You can customize the location or switch databases anytime by editing `.env`:
```env
# Option A: SQLite (Default Relational DB file)
DATABASE_URL="sqlite:///./certificates.db"

# Option B: MySQL Server
# DATABASE_URL="mysql+pymysql://root:password@localhost:3306/certificates_db"
```

When the application boots (`app/main.py` lifespan), `init_db()` is automatically executed:
```python
def init_db() -> None:
    Base.metadata.create_all(bind=engine)
```
This inspects your models and automatically creates the tables in the database if they do not exist yet.

### 3. How Data is Stored in the Database

Data insertion and updates are performed using **SQLAlchemy ORM** in [app/services/job_service.py](file:///d:/bulk-certificate-generator/app/services/job_service.py):

#### Step A: Storing the Generation Job
When a bulk request arrives, `JobService.create_job` creates a new `GenerationJob` record:
```python
job = GenerationJob(
    id=str(uuid.uuid4()),
    title=request.title,
    issuer_name=request.issuer_name,
    status=JobStatus.PENDING,
    total_records=len(request.recipients),
    created_at=datetime.now(timezone.utc),
)
db.add(job)
db.flush()  # Assigns job.id to link recipient records
```

#### Step B: Storing Individual Certificate Records
For each valid recipient in the request, a `Certificate` record is created with a foreign key referencing `job.id`:
```python
for rec in valid_recipients:
    cert = Certificate(
        id=str(uuid.uuid4()),
        job_id=job.id,  # Foreign key linking back to GenerationJob
        recipient_name=rec.name,
        recipient_email=rec.email,
        status=CertificateStatus.PENDING,
        verification_code=generate_verification_code(),
    )
    db.add(cert)

db.commit()  # Atomically saves all records to the database
```

#### Step C: Updating Statuses During Background Processing
As each certificate PDF is rendered, its individual record is updated and committed independently to provide fault isolation:
```python
cert.status = CertificateStatus.SUCCESS
cert.file_path = pdf_metadata["file_path"]
cert.file_size_bytes = pdf_metadata["file_size_bytes"]
db.commit()
```

### 4. How Data is Retrieved from the Database

The database session is provided to API endpoints using FastAPI's dependency injection (`db: Session = Depends(get_db)`):

* **Retrieve a Job by ID**:
  ```python
  job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
  ```
* **Retrieve All Certificates for a Job (via ORM Relationship)**:
  ```python
  # Accesses all certificates related to this job via the foreign key
  certificates = job.certificates
  ```
* **Retrieve a Single Certificate by ID (for PDF Download)**:
  ```python
  cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
  ```
* **Retrieve by Public Verification Code (for Authenticity Verification)**:
  ```python
  cert = db.query(Certificate).filter(Certificate.verification_code == code).first()
  ```
* **List and Filter Certificates with Pagination**:
  ```python
  query = db.query(Certificate)
  if job_id:
      query = query.filter(Certificate.job_id == job_id)
  if status:
      query = query.filter(Certificate.status == status)
  certs = query.order_by(Certificate.created_at.desc()).offset(skip).limit(limit).all()
  ```

### 5. How to Switch to MySQL (if required)

Because the project is architected with **SQLAlchemy ORM**, switching from SQLite to MySQL requires **zero changes to Python code**:

1. **Create the Database in MySQL**:
   ```sql
   CREATE DATABASE certificates_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
2. **Update `.env`**:
   ```env
   DATABASE_URL="mysql+pymysql://root:yourpassword@localhost:3306/certificates_db"
   ```
3. **Start the App**:
   ```bash
   uvicorn app.main:app --reload
   ```
   SQLAlchemy automatically connects to MySQL via `pymysql` and generates the `generation_jobs` and `certificates` tables with all indexes and constraints.

### 6. How to View and Inspect the Database
To view the data stored inside `certificates.db`:
* **VS Code Extension**: Install the **SQLite Viewer** or **SQLTools** extension to browse tables and rows directly inside your editor.
* **GUI Tools**: Open `certificates.db` with [DB Browser for SQLite](https://sqlitebrowser.org/) or [DBeaver](https://dbeaver.io/).
* **Python Quick Inspection**:
  ```bash
  python -c "from app.database import SessionLocal; from app.models.generation_job import GenerationJob; db = SessionLocal(); print(f'Total Jobs: {db.query(GenerationJob).count()}')"
  ```

---

## Running the Application

Start the Uvicorn ASGI development server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running, access the following URLs in your browser:
* **Interactive UI Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard) (or `/login`)
* **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### UI Dashboard Login Credentials
When opening the **UI Dashboard** (`/dashboard` or `/login`), sign in using the following administrative credentials:

| Field | Default Value | Notes |
| :--- | :--- | :--- |
| **Username / Email** | `admin` (or `admin@example.com`) | Case-insensitive |
| **Password** | `admin123` | Secure demonstration password |
| **Role** | `Administrator` | Full administrative privileges |

> [!TIP]
> **One-Click Demo Login**: The login screen features a **"⚡ Fill Demo Credentials"** button that automatically pre-fills the login fields so evaluators can access the dashboard instantly with zero typing.
> Clicking **Logout** in the bottom-left sidebar terminates the session and returns you to the login screen.


---

## How to Submit a Certificate Generation Request

### Method 1: Interactive Web Dashboard (UI)

The system provides a full-featured web dashboard at [http://localhost:8000/dashboard](http://localhost:8000/dashboard) (or `/login`).

#### Step 1: Sign In via Administrator Portal
Sign in using `admin` / `admin123` (or click **"⚡ Fill Demo Credentials"** for 1-click access):

![Login Screen](docs/images/06_login_screen.png)

#### Step 2: Open Bulk Generation & Enter Job Information
1. Click **Bulk Generation** in the left sidebar navigation.
2. Enter the **Job Name**, **Course Name**, and **Completion Date**.
3. Upload recipients via drag-and-drop CSV (or click one of the quick test presets: `🟢 All Pass`, `🟡 Some Failed`, or `🔴 All Failed`):

![Bulk Generation Wizard](docs/images/02_bulk_generation_wizard.png)

#### Step 3: Review & Submit Generation Batch
Review validated recipients and click **Start Generation 🚀**. The job will immediately begin processing with independent fault isolation:

#### Step 4: Monitor Live Progress & Download Certificates
The dashboard transitions to **Job Status & Progress** to track real-time generation progress, pass/fail counts, and status badges:

![Job Status & Progress](docs/images/03_job_status_progress.png)

Click **View** on any job row to slide open the **Job Details Drawer**, revealing recipient-level status, failure reasons, and instant **PDF ↓** and **PNG ↓** download options:

![Job Details Drawer](docs/images/04_job_detail_drawer.png)

---

### Method 2: Programmatic REST API (cURL / HTTP)

Submit a bulk certificate generation request using `POST /api/v1/certificate-jobs`:

#### cURL Request:
```bash
curl -X POST "http://localhost:8000/api/v1/certificate-jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "job_name": "Python Training Program",
    "course_name": "Python Programming",
    "completion_date": "2026-10-10",
    "issuer_name": "Global Tech Academy",
    "signatory_name": "Dr. Sarah Mitchell",
    "signatory_title": "Head of Certification",
    "recipients": [
      {
        "name": "Rahul Sharma",
        "email": "rahul@example.com"
      },
      {
        "name": "Priya Verma",
        "email": "priya@example.com"
      },
      {
        "name": "Amit Patel",
        "email": "amit@example.com",
        "extra_data": {"grade": "A+", "honors": "Distinction"}
      }
    ]
  }'
```

#### Synchronous Mode:
Add `?sync=true` to process immediately and receive completed certificate URLs in the response:
```bash
curl -X POST "http://localhost:8000/api/v1/certificate-jobs?sync=true" \
  -H "Content-Type: application/json" \
  -d '{ ... }'
```

#### Response (`HTTP 202 Accepted`):
```json
{
  "id": "JOB-1",
  "job_id": "JOB-1",
  "title": "Python Training Program",
  "job_name": "Python Training Program",
  "course_name": "Python Programming",
  "issuer_name": "Global Tech Academy",
  "status": "PENDING",
  "total_records": 3,
  "total_recipients": 3,
  "valid_records": 3,
  "invalid_records": 0,
  "processed_records": 0,
  "successful_records": 0,
  "successful_count": 0,
  "failed_records": 0,
  "failed_count": 0,
  "progress_percentage": 0.0,
  "message": "Certificate generation job created and dispatched to background workers.",
  "created_at": "2026-10-11T11:00:00Z",
  "updated_at": "2026-10-11T11:00:00Z"
}
```

---

## Tracking Status & Retrieving Generated Certificates

### 1. Check Overall Job Status & Progress
```bash
curl -X GET "http://localhost:8000/api/v1/certificate-jobs/{job_id}"
```
Returns overall status (`PROCESSING`, `COMPLETED`, `PARTIALLY_COMPLETED`), counts, and progress percentage.

### 2. List All Certificates for a Job
```bash
curl -X GET "http://localhost:8000/api/v1/certificate-jobs/{job_id}/certificates"
```
Returns an array of all recipient records with their individual status (`SUCCESS`, `FAILED`, `PENDING`), download URLs, verification codes, and error messages (if failed).

### 3. Download a Single Certificate (PDF or PNG Options)

You have the choice to download certificates in either **PDF** format (vector print-ready) or **PNG** format (high-resolution image) using query parameters or direct endpoints:

#### Option A: Download as PDF
```bash
# Via query parameter (default is PDF)
curl -X GET "http://localhost:8000/api/v1/certificates/{certificate_id}/download?format=pdf" -O -J

# Or direct PDF route
curl -X GET "http://localhost:8000/api/v1/certificates/{certificate_id}/download/pdf" -O -J
```
Returns `Content-Type: application/pdf` with print-ready vector layout.

#### Option B: Download as PNG
```bash
# Via query parameter
curl -X GET "http://localhost:8000/api/v1/certificates/{certificate_id}/download?format=png" -O -J

# Or direct PNG route
curl -X GET "http://localhost:8000/api/v1/certificates/{certificate_id}/download/png" -O -J
```
Returns `Content-Type: image/png` rendered in high-definition (144+ DPI) for web sharing and social media.

### 4. Download All Certificates as a ZIP Archive (PDF or PNG)
```bash
# Download all certificates as PDF in ZIP (default)
curl -X GET "http://localhost:8000/api/v1/jobs/{job_id}/download-all?format=pdf" -O -J

# Download all certificates as PNG in ZIP
curl -X GET "http://localhost:8000/api/v1/jobs/{job_id}/download-all?format=png" -O -J

# Download all certificates in both PDF and PNG formats
curl -X GET "http://localhost:8000/api/v1/jobs/{job_id}/download-all?format=all" -O -J
```
Packages all successfully generated certificates in the batch into a single `.zip` file for 1-click batch distribution.

### 5. Verify Certificate Authenticity (Public Endpoint)
```bash
curl -X GET "http://localhost:8000/api/v1/certificates/verify/{verification_code}"
```
Used by QR code scanners and employers to verify that the certificate was legitimately issued.

---

## Comprehensive Test Cases & Scenarios (All Pass, Some Failed, All Failed)

To thoroughly validate batch processing and fault isolation, the application comes with **3 dedicated test scenarios** representing every possible batch generation outcome:

| Scenario | Job Title & ID | Total | Passed | Failed | Final Status | Key Verification Objective |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Test Case 1: All Pass** | `Python Full Stack Bootcamp` (`JOB-1`) | 4 | 4 | 0 | `COMPLETED` | 100% success rate; all PDFs and PNGs generated and downloadable. |
| **Test Case 2: Some Failed** | `Cloud & DevOps Masterclass` (`JOB-2`) | 5 | 3 | 2 | `PARTIALLY_COMPLETED` | **Fault Isolation**: Failures on individual recipients do not block valid recipients. Error reasons are logged per recipient. |
| **Test Case 3: All Failed** | `Cybersecurity Penetration Testing` (`JOB-3`) | 3 | 0 | 3 | `FAILED` | 0% success rate; entire batch fails gracefully without application crash; clear error messages displayed. |

---

### How to Trigger & Display Test Scenarios in the Dashboard

You can seed or run these test cases through the UI in multiple ways:

#### Option 1: 1-Click "Seed Test Scenarios" Button
* Navigate to **Dashboard Overview** or **Job Status & Progress** (`/dashboard`).
* Click the **"🧪 Seed Test Scenarios"** button located in the top action bar or filter header.
* This calls `POST /api/v1/jobs/seed-test-scenarios?clear_existing=true`, resetting the database with the three canonical test jobs:
  1. **JOB-1** (`COMPLETED` - 4/4 passed)
  2. **JOB-2** (`PARTIALLY_COMPLETED` - 3 passed, 2 failed with distinct error reasons)
  3. **JOB-3** (`FAILED` - 0 passed, 3 failed)
* The dashboard overview KPI cards, status donut chart (displaying green, amber, and red slices), and job tables immediately update with real-time statistics.

#### Option 2: 1-Click Generation Wizard Presets (Screen 2)
* Go to **Bulk Generation** in the sidebar.
* In **Step 2 (Recipients)**, click one of the quick test buttons:
  - **`🟢 All Pass (4)`**: Loads 4 valid recipients.
  - **`🟡 Some Failed (5)`**: Loads 3 valid recipients and 2 recipients pre-configured with simulated rendering failures.
  - **`🔴 All Failed (3)`**: Loads 3 recipients configured to fail.
* Click **Start Generation** to watch the job execute in real-time.

#### Option 3: Via Programmatic REST API
```bash
# Seed all 3 test scenarios into the database
curl -X POST "http://localhost:8000/api/v1/jobs/seed-test-scenarios?clear_existing=true"
```

---

## Running Automated Tests

The test suite covers all requirements including job creation, input validation, PDF generation, status polling, fault isolation, and retrieval.

Run the entire test suite using `pytest`:

```bash
python -m pytest -v
```

### Test Coverage Highlights (30 Automated Tests):
* `tests/test_jobs.py`:
  - **Scenario 1 - All Pass**: `test_job_scenario_all_certificates_pass` verifies 100% success rate and `COMPLETED` status.
  - **Scenario 2 - Some Failed**: `test_job_scenario_some_certificates_failed_partial_completed` verifies fault isolation, individual error logging, and `PARTIALLY_COMPLETED` status.
  - **Scenario 3 - All Failed**: `test_job_scenario_all_certificates_failed` verifies graceful handling of 100% failed batches and `FAILED` status.
  - **Test Seeding Endpoint**: `test_seed_test_scenarios_api_endpoint` verifies `POST /api/v1/jobs/seed-test-scenarios`.
  - Bulk job creation & background task queuing
  - Input validation (empty recipient list, blank title, invalid email format, empty recipient name)
  - Non-existent job 404 handling
  - Pagination for job lists
* `tests/test_generation.py`:
  - Direct ReportLab PDF vector generation
  - PDF binary `%PDF` magic bytes verification
  - Extra metadata rendering (grades, honors)
* `tests/test_downloads.py`:
  - Single certificate downloads in both PDF and PNG formats (`?format=pdf`, `?format=png`)
  - Direct routes `/download/pdf` and `/download/png`
  - Batch ZIP archive bundling in PDF and PNG formats
  - Non-existent certificate 404 handling

---

## Interactive UI Dashboards Overview

The application includes a complete web frontend accessible at `/dashboard` that faithfully implements the 4 reference screens from the specification:

### 1. Dashboard Overview
System statistics (total jobs, total recipients, success rate), status distribution donut chart with partial failure slice, recent activity feed, and latest jobs table:

![Dashboard Overview](docs/images/01_dashboard_overview.png)

### 2. Bulk Certificate Generation
3-step wizard supporting event metadata, CSV drag-and-drop upload, 1-click test scenario presets (`🟢 All Pass`, `🟡 Some Failed`, `🔴 All Failed`), sample CSV download, and real-time validation preview:

![Bulk Certificate Generation](docs/images/02_bulk_generation_wizard.png)

### 3. Job Status & Progress
Live job tracking with status filters (`ALL`, `COMPLETED`, `PARTIAL`, `FAILED`), dynamic progress bars, and expandable recipient details with both PDF and PNG ZIP and individual downloads:

![Job Status & Progress](docs/images/03_job_status_progress.png)

### 4. Certificate Management
Searchable and filterable registry of all issued certificates with instant preview and dual format download buttons (`PDF ↓` or `PNG ↓`):

![Certificate Management](docs/images/05_certificate_management.png)

---

## 10 Critical Interview & Design Questions (Answered)

### 1. Why did you choose FastAPI instead of Flask or Django REST Framework?
FastAPI was selected for three core reasons:
1. **Asynchronous Architecture (`asyncio`)**: Native non-blocking I/O and built-in `BackgroundTasks` allow long-running bulk PDF generation to execute in the background without blocking API request threads.
2. **Automatic Request Validation**: Powered by Pydantic v2, incoming request payloads are strictly validated at the boundary before touching the database or business logic, returning clear, structured error responses.
3. **Automatic OpenAPI/Swagger Documentation**: Interactive API documentation is automatically generated at `/docs`, simplifying testing and client integration.

### 2. Why did you create separate job and certificate tables?
A bulk request is inherently a **one-to-many** domain model.
- `generation_jobs` holds aggregate state: event details, batch progress, overall status, total count, successful count, and failed count.
- `certificates` (`certificate_records`) holds recipient-level state: recipient name, email, generated PDF file path, individual status, verification code, and error messages.
Separating them ensures:
- Database normalization without data duplication.
- Granular tracking where an issue with one certificate can be logged and inspected independently.
- Fast queries for both high-level job summaries and individual recipient lookups.

### 3. How do you handle one failed certificate without stopping the batch?
Within `JobService.process_job`, the recipient loop executes each certificate generation inside an isolated `try/except Exception` block:
```python
for cert in pending_certs:
    try:
        pdf_meta = CertificateGenerator.generate(...)
        cert.status = CertificateStatus.SUCCESS
        cert.file_path = pdf_meta["file_path"]
        successful_count += 1
    except Exception as exc:
        cert.status = CertificateStatus.FAILED
        cert.error_message = str(exc)
        failed_count += 1
    db.commit()
```
Because each iteration commits its own result and catches any rendering exception, an error on recipient #3 has zero impact on recipients #1, #2, #4, and #5. At the end of the batch, the job status is set to `COMPLETED` (if all succeed), `PARTIALLY_COMPLETED` (if some succeed and some fail), or `FAILED` (if all fail).

### 4. How do you calculate job progress accurately?
Job progress is calculated in real time using the formula:
$$\text{progress\_percentage} = \min\left(100.0, \frac{\text{successful\_count} + \text{failed\_count}}{\text{total\_records}} \times 100\right)$$
As each recipient completes (whether succeeding or failing), `processed_records` is incremented. Clients polling `GET /api/v1/certificate-jobs/{job_id}` receive an up-to-date percentage and exact counts without waiting for the entire batch to complete.

### 5. What happens if the application restarts while a job is processing?
If the server crashes mid-generation, in-flight jobs remain in the `PROCESSING` state in the database.
To handle this cleanly:
- On startup, the application identifies jobs stuck in `PROCESSING` whose worker has terminated.
- Because each certificate record tracks its own status (`SUCCESS`, `FAILED`, `PENDING`), recovery is straightforward: only records still marked `PENDING` need to be resumed, avoiding duplicate rendering for already completed certificates.

### 6. How would you handle 10,000 recipients?
For production at scale:
1. **Durable Distributed Queue**: Replace in-memory `BackgroundTasks` with **Celery** or **ARQ** backed by **Redis** or **RabbitMQ**.
2. **Chunked Task Fan-out**: Split 10,000 recipients into batches of 100 and dispatch them across multiple Celery worker processes.
3. **Cloud Object Storage**: Stream generated PDFs directly to **Amazon S3** or **Google Cloud Storage** with pre-signed download URLs rather than storing them on local disk.
4. **Rate Limiting & Concurrency Bounds**: Limit simultaneous PDF render operations to prevent CPU starvation.

### 7. How would you prevent duplicate jobs or duplicate certificates?
1. **Idempotency Keys**: Accept an `Idempotency-Key` HTTP header. If a request with the same key arrives within a specified TTL, return the existing job record immediately.
2. **Unique Composite Index**: Place a unique database constraint on `(job_id, recipient_email)` to guarantee that the same recipient cannot be added twice to the same generation job.
3. **Deterministic Verification Codes**: Hash the recipient email and event ID with a secret salt to generate deterministic, unforgeable verification codes.

### 8. How do you safely store and serve generated PDF files?
1. **Sanitized File Paths**: Store files with UUID-based or hashed filenames (e.g., `cert_{job_id}_{hash}.pdf`) rather than raw user-supplied strings, completely preventing path traversal vulnerabilities (`../`).
2. **Streaming via FileResponse**: Serve files using FastAPI's `FileResponse` with explicit MIME type `application/pdf` and `Content-Disposition: attachment`.
3. **Access Controls**: In production, certificates can be gated behind bearer tokens or expiring pre-signed URLs.

### 9. How would you test a PDF-generation failure?
Using Python's `unittest.mock.patch` to mock `CertificateGenerator.generate` and simulate an exception for specific input conditions.
This is implemented in `tests/test_jobs.py`:
```python
def mock_generate_with_single_failure(*args, **kwargs):
    if kwargs.get("recipient_name") == "Recipient 3 (Crash)":
        raise RuntimeError("Simulated render engine crash")
    return original_generate(*args, **kwargs)

with patch.object(CertificateGenerator, "generate", side_effect=mock_generate_with_single_failure):
    response = client.post("/api/v1/certificate-jobs?sync=true", json=payload)
    assert response.json()["status"] == "PARTIALLY_COMPLETED"
```

### 10. How would you change the system to email certificates after generation?
1. **Email Service Integration**: Introduce an `EmailService` integrating with an SMTP server or transactional provider (SendGrid, AWS SES, Brevo).
2. **Background Dispatch**: After a certificate is marked `SUCCESS` and its PDF is saved, trigger an asynchronous email dispatch event attaching the PDF or providing a direct download link.
3. **Delivery Tracking**: Add `email_status` (`PENDING`, `SENT`, `BOUNCED`, `FAILED`) to the `certificates` table so email delivery failures are tracked independently of PDF generation success.

---

## License

This project is licensed under the MIT License.