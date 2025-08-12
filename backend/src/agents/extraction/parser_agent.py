import logging
import os
import fitz  # PyMuPDF
import boto3
from src.core.config import settings

logger = logging.getLogger(__name__)

# NODE 1: Downloader
def downloader_node(state: dict) -> dict:
    """
    Downloads the document from MinIO storage to a temporary local path.
    """
    job_id = state["job_id"]
    s3_path = state["s3_path"]
    logger.info(f"[Node: Downloader, Job: {job_id}] Starting download from {s3_path}.")
    
    try:
        # Assumes s3_path is like "s3://bucket_name/object_name"
        bucket_name = s3_path.split('/')[2]
        object_name = '/'.join(s3_path.split('/')[3:])

        s3 = boto3.client(
            "s3", 
            endpoint_url=f"http://{settings.MINIO_HOST}", 
            aws_access_key_id=settings.MINIO_ROOT_USER, 
            aws_secret_access_key=settings.MINIO_ROOT_PASSWORD
        )
        
        temp_dir = "/tmp/processing_files"
        os.makedirs(temp_dir, exist_ok=True)
        local_path = os.path.join(temp_dir, f"{job_id}_document.pdf")

        s3.download_file(bucket_name, object_name, local_path)
        
        logger.info(f"[Node: Downloader, Job: {job_id}] File downloaded to {local_path}.")
        state["local_path"] = local_path
        state["error"] = None
    except Exception as e:
        error_message = f"Failed to download from MinIO. Error: {e}"
        logger.error(f"[Node: Downloader, Job: {job_id}] {error_message}")
        state["error"] = error_message
        
    return state

# NODE 2: Parser
def parser_node(state: dict) -> dict:
    """
    Parses the downloaded PDF into text chunks, page by page.
    """
    if state.get("error"): return state
    job_id = state["job_id"]
    local_path = state["local_path"]
    logger.info(f"[Node: Parser, Job: {job_id}] Starting PDF parsing for {local_path}.")
    
    parsed_chunks = []
    try:
        document = fitz.open(local_path)
        for page_num in range(len(document)):
            page = document.load_page(page_num)
            text = page.get_text()
            if text.strip(): # Only add chunks with actual text content
                parsed_chunks.append({
                    "page_number": page_num + 1,
                    "text": text,
                    "source": local_path
                })
        
        logger.info(f"[Node: Parser, Job: {job_id}] Parsed {len(parsed_chunks)} pages.")
        state["parsed_chunks"] = parsed_chunks
        state["error"] = None
    except Exception as e:
        error_message = f"Failed to parse PDF. Error: {e}"
        logger.error(f"[Node: Parser, Job: {job_id}] {error_message}")
        state["error"] = error_message
        
    return state

# NODE 3: Cleanup for this pipeline
def processing_cleanup_node(state: dict) -> dict:
    """
    Deletes the temporary local file after processing.
    """
    if not state.get("local_path"): return state
    job_id = state["job_id"]
    local_path = state["local_path"]
    logger.info(f"[Node: ProcessingCleanup, Job: {job_id}] Deleting temp file.")
    try:
        if os.path.exists(local_path):
            os.remove(local_path)
    except Exception as e:
        logger.warning(f"[Node: ProcessingCleanup, Job: {job_id}] Failed to delete temp file: {e}")
    return state
# ... (downloader_node, parser_node, and processing_cleanup_node are here) ...

# NEW NODE FOR DEBUGGING! not for production use
def log_parser_output_node(state: dict) -> dict:
    """
    A simple node that prints the parsed chunks to the console for verification.
    """
    if state.get("error"): return state
    job_id = state["job_id"]
    parsed_chunks = state.get("parsed_chunks", [])
    
    logger.info(f"--- PARSED OUTPUT FOR JOB {job_id} ---")
    if not parsed_chunks:
        logger.info("No chunks were parsed.")
    else:
        logger.info(f"Successfully parsed {len(parsed_chunks)} chunks.")
        # Print the first 500 characters of the first page for a quick preview
        first_chunk_text = parsed_chunks[0].get("text", "")[:500]
        logger.info("--- Preview of Page 1 ---")
        logger.info(f"{first_chunk_text}...")
        logger.info("-----------------------------")

    return state