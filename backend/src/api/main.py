from fastapi import FastAPI
from .endpoints import router as api_router # Import the router we just made

# App instantiation
app = FastAPI(
    title="Structuring the Unstructured API",
    description="API for the Multi-Agent Financial KPI Extraction System.",
    version="1.0.0",
)

# Include the API router
# All routes defined in endpoints.py will now be part of the app
app.include_router(api_router, prefix="/api/v1", tags=["Document Processing"])


@app.get("/", tags=["Health Check"])
def health_check():
    """A simple health check endpoint."""
    return {"status": "ok"}