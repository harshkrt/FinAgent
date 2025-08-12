import logging
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks

from src.pipelines.extraction_pipeline import ingestion_trigger_app

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["Document Processing"]
)

@router.post("/process-document", status_code=status.HTTP_202_ACCEPTED)
async def process_document_endpoint(
    background_tasks: BackgroundTasks,
    url: str = Form(None), 
    file: UploadFile = File(None)
):
    if not url and not file:
        raise HTTPException(status_code=400, detail="Provide either 'url' or 'file'.")
    if url and file:
        raise HTTPException(status_code=400, detail="Provide 'url' OR 'file', not both.")

    job_id = str(uuid.uuid4())
    
    if file:
        initial_state = {"job_id": job_id, "source_type": "upload", "input_data": await file.read(), "filename": file.filename}
    else:
        initial_state = {"job_id": job_id, "source_type": "url", "input_data": url, "filename": url.split('/')[-1] or "downloaded_file"}
    
    logger.info(f"Accepted job {job_id} for {initial_state['source_type']}: {initial_state['filename']}")

    background_tasks.add_task(ingestion_trigger_app.invoke, initial_state)

    return {"message": "Document accepted for processing. Pipeline started.", "job_id": job_id, "source": initial_state['filename']}