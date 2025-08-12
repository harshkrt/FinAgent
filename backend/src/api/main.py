import logging
from fastapi import FastAPI
from . import endpoints
from src.pipelines.extraction_pipeline import ingestion_trigger_app, processing_app
#from langgraph.server import add_api_routes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FinAgent API",
    description="An intelligent agent system for financial document analysis.",
    version="1.0.0"
)

@app.get("/", tags=["Status"])
def read_root():
    return {"status": "FinAgent API is running"}

# # ================================================================
# # == Expose LangGraph Pipelines to LangGraph Studio
# # ================================================================

# # This adds API routes for the first pipeline at /ingestion-trigger/...
# add_api_routes(
#     app, 
#     ingestion_trigger_app, 
#     path="/ingestion-trigger",
#     # You can add more config here if needed, like input/output schemas
#     # config_keys=["configurable"] 
# )

# # This adds API routes for the second pipeline at /document-processor/...
# add_api_routes(
#     app, 
#     processing_app, 
#     path="/document-processor",
# )

# # NOTE: The original /api/v1/process-document endpoint is in endpoints.py
# # We keep it separate because it's the public-facing trigger, while these
# # new routes are for debugging with the Studio.

app.include_router(endpoints.router)