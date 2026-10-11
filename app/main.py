from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.routers import jobs, certificates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager: handles startup and shutdown."""
    settings.init_directories()
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## Bulk Certificate Generator API
    
    A resilient backend system for generating and managing bulk certificate issuance.
    
    ### Key Features:
    * **Bulk Generation**: Submit multiple recipients in a single request.
    * **Strict Input Validation**: Validates recipient names, emails, and parameters.
    * **Fault Isolation**: Generation failures on individual records do not crash or abort the batch.
    * **Async / Background Processing**: Non-blocking generation with real-time progress tracking.
    * **Professional PDF Certificates**: ReportLab-powered certificates with ornamental borders, typography, and QR code verification.
    * **Single & Batch Retrieval**: Download individual PDF certificates or all certificates bundled as a ZIP archive.
    * **Public Verification Endpoint**: Real-time authenticity verification by unique certificate code.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers directly from app.routers
app.include_router(jobs.router, prefix=f"{settings.API_V1_PREFIX}/certificate-jobs", tags=["Certificate Jobs"])
app.include_router(jobs.router, prefix=f"{settings.API_V1_PREFIX}/jobs", tags=["Jobs"])
app.include_router(certificates.router, prefix=f"{settings.API_V1_PREFIX}/certificates", tags=["Certificates"])

# Mount Static Assets & UI Dashboard
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/dashboard", tags=["UI Dashboard"], response_class=FileResponse)
@app.get("/ui", tags=["UI Dashboard"], response_class=FileResponse)
@app.get("/login", tags=["UI Dashboard"], response_class=FileResponse)
def dashboard_page():
    """Interactive Management Dashboard with real-time stats, bulk generator, and certificate viewer."""
    index_file = static_dir / "index.html"
    return FileResponse(index_file)


@app.get("/", tags=["General"])
def root_endpoint():
    """Welcome and API documentation link."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "dashboard_url": "/dashboard",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "api_v1": settings.API_V1_PREFIX,
    }


@app.get("/health", tags=["General"])
def health_check():
    """Health check endpoint to verify system status."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
