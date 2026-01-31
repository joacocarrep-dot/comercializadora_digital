import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.api.v1.health import router as health_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Comercializadora API",
    description="Backend de la comercializadora digital",
    version="1.0.0",
)

# Configure CORS middleware (allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include health router under /api/v1 prefix
app.include_router(health_router, prefix="/api/v1", tags=["health"])

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to /docs"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")