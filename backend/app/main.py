import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.api.v1.health import router as health_router
from app.api.v1.admin.auth import router as auth_router
from app.api.v1.admin.suppliers import router as suppliers_router
from app.api.v1.admin.storefronts import router as storefronts_router
from app.core.exceptions import (
    ComercializadoraException,
    comercializadora_exception_handler,
    general_exception_handler,
    http_exception_handler,
)
from app.core.middleware import RequestLoggingMiddleware, StorefrontMiddleware

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

# Add custom middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(StorefrontMiddleware)

# Register exception handlers
app.add_exception_handler(ComercializadoraException, comercializadora_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include health router under /api/v1 prefix
app.include_router(health_router, prefix="/api/v1", tags=["health"])

# Include admin routers under /api/v1/admin prefix
app.include_router(auth_router, prefix="/api/v1/admin", tags=["admin-auth"])
app.include_router(suppliers_router, prefix="/api/v1/admin/suppliers", tags=["admin-suppliers"])
app.include_router(storefronts_router, prefix="/api/v1/admin/storefronts", tags=["admin-storefronts"])

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to /docs"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
