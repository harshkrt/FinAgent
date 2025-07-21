import shutil
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import Optional

# This router will contain all our API endpoints
router = APIRouter()

@router.post("/process-document", status_code=status.HTTP_202_ACCEPTED)
async def process_document_endpoint(
    source_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Accepts a document for processing either from a URL or a direct file upload.

    This is the main ingestion endpoint for the system. It will perform initial validation
    and then hand off the document to the background processing pipeline.

    - **source_url**: URL of a PDF/HTML document to fetch.
    - **file**: A direct file upload (e.g., a PDF).

    A 202 Accepted response is returned immediately, and processing happens
    asynchronously.
    """
    # 1. --- Basic Input Validation ---
    if not source_url and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a 'source_url' or a 'file' must be provided."
        )

    if source_url and file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a 'source_url' or a 'file', not both."
        )

    # 2. --- Logic for Handling the Input ---
    # At this point, you have either a URL or a file object.
    # The next step (Task T7/T8) will be to hand this off to the appropriate agents.

    if file:
        # For a file upload, we can get its filename and content type
        filename = file.filename
        content_type = file.content_type
        print(f"Received uploaded file: {filename} ({content_type})")
        
        # --- Placeholder for Agent Call (T7) ---
        # In a real scenario, you would NOT save the file here directly.
        # You would pass the `file` object to the Source Handler/Fetcher Agent.
        # For now, we can just simulate saving it to a temporary location to verify.
        temp_file_path = f"/tmp/{filename}"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # This will be replaced by:
        # result = await source_handler_agent.process_uploaded_file(file)
        # ----------------------------------------
        
        return {"message": "File uploaded and accepted for processing.", "filename": filename}

    if source_url:
        # For a URL, we have the string
        print(f"Received source URL: {source_url}")
        
        # --- Placeholder for Agent Call (T7) ---
        # This will be replaced by:
        # result = await source_handler_agent.process_url(source_url)
        # ----------------------------------------

        return {"message": "URL received and accepted for processing.", "url": source_url}