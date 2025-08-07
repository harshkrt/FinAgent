from fastapi import (
    APIRouter, 
    UploadFile, 
    File, 
    Form, 
    HTTPException, 
    status, 
    Depends
)
from agents.extraction.source_handler_agent import SourceHandlerAgent
from typing import Optional
from pydantic import HttpUrl

# This router will be included by the main FastAPI app
router = APIRouter()


def get_source_handler_agent():
    # dependency provider for the SourceHandlerAgent
    try:
        return SourceHandlerAgent()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Configuration error of SourceHandlerAgent: {e}")

@router.post(
    "/process-document",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Accept and process a financial document"
)

async def process_document_endpoint(
     source_url: Optional[str] = Form(None, description="URL of a PDF/HTML document to fetch."),
    file: Optional[UploadFile] = File(None, description="A direct file upload (e.g., a PDF)."),
    agent: SourceHandlerAgent = Depends(get_source_handler_agent)
): 
    s3_path: Optional[str] = None

    if not source_url and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'source_url' or 'file' must be provided."
        )
        
    if source_url and file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'source_url' or 'file' must be provided"
        )
    
    try:
        # The 'if file:' block should ONLY contain the logic for the file case
        if file:
            print("Processing direct file upload...")
            
            # Step 1: Validate the file
            agent.validate_file(file)
            
            # Step 2: Store the file (ONCE!)
            s3_path = agent.upload_file_to_storage(file)
        
        elif source_url:
            print("Processing URL upload...")
            # The URL handler takes care of its own validation and storage
            s3_path = await agent.handle_url(str(source_url))
        
        # This check happens AFTER the if/elif block
        if not s3_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store the document."
            )
        
        # Now, trigger the background job
        print(f"Document stored at {s3_path}. Triggering processing queue.")
        agent.publish_to_processing_queue(s3_path)
        
        return {
            "message": "Document accepted for background processing.",
            "s3_path": s3_path,
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"An unexpected error occurred in the endpoint: {e}")
        # We can see the specific error here thanks to the log
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}"
        )