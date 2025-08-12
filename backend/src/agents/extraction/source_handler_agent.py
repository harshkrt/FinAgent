import logging
import os
import json
from typing import TypedDict, Union
from botocore.client import Config
import boto3
import httpx
import pika
from src.core.config import settings

logger = logging.getLogger(__name__)

# The 'state' that gets passed between the nodes in this specific pipeline
class IngestionState(TypedDict):
    job_id: str
    source_type: str
    input_data: Union[str, bytes]
    filename: str
    temp_file_path: str
    s3_path: str
    error: str

# NODE 1: Fetcher
def fetcher_node(state: IngestionState) -> IngestionState:
    job_id, source_type, input_data, filename = state["job_id"], state["source_type"], state["input_data"], state["filename"]
    logger.info(f"[Node: Fetcher, Job: {job_id}] Starting fetch for {source_type}.")
    
    temp_dir = "/tmp/ingestion_files"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, f"{job_id}_{filename}")

    try:
        if source_type == "upload":
            with open(temp_file_path, "wb") as buffer: buffer.write(input_data)
        elif source_type == "url":
            with httpx.stream("GET", input_data, follow_redirects=True, timeout=30) as r:
                r.raise_for_status()
                with open(temp_file_path, "wb") as buffer:
                    for chunk in r.iter_bytes(): buffer.write(chunk)
        
        logger.info(f"[Node: Fetcher, Job: {job_id}] Document saved to: {temp_file_path}")
        state["temp_file_path"] = temp_file_path
        state["error"] = None
    except Exception as e:
        state["error"] = f"Failed to fetch document. Error: {e}"
        logger.error(f"[Node: Fetcher, Job: {job_id}] {state['error']}")
    return state

# NODE 2: Archiver (Final, Robust Version)
def archiver_node(state: IngestionState) -> IngestionState:
    if state.get("error"):
        return state
    job_id, temp_file_path, filename = state["job_id"], state["temp_file_path"], state["filename"]
    logger.info(f"[Node: Archiver, Job: {job_id}] Archiving to MinIO.")
    
    try:
        s3 = boto3.client(
            "s3", 
            endpoint_url=f"http://{settings.MINIO_HOST}",
            aws_access_key_id=settings.MINIO_ROOT_USER, 
            aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
            config=Config(signature_version='s3v4')
        )
        bucket = settings.S3_BUCKET_NAME
        object_name = f"raw_filings/{job_id}/{filename}"
        
        try: 
            s3.head_bucket(Bucket=bucket)
        except Exception: 
            logger.info(f"Bucket '{bucket}' not found. Creating it.")
            s3.create_bucket(Bucket=bucket)
            
        s3.upload_file(temp_file_path, bucket, object_name)
        
        state["s3_path"] = f"s3://{bucket}/{object_name}"
        logger.info(f"[Node: Archiver, Job: {job_id}] File archived to: {state['s3_path']}")
        state["error"] = None
    except Exception as e:
        state["error"] = f"Failed to archive file. Error: {e}"
        logger.error(f"[Node: Archiver, Job: {job_id}] {state['error']}")
    return state


# NODE 3: Trigger
def trigger_node(state: IngestionState) -> IngestionState:
    if state.get("error"):
        return state
    job_id, s3_path = state["job_id"], state["s3_path"]
    logger.info(f"[Node: Trigger, Job: {job_id}] Publishing job to RabbitMQ.")
    
    try:
        creds = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
        conn = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq_broker', credentials=creds))
        ch = conn.channel()
        q_name = "document_processing_queue"
        ch.queue_declare(queue=q_name, durable=True)
        msg = {"job_id": job_id, "s3_path": s3_path}
        ch.basic_publish(exchange='', routing_key=q_name, body=json.dumps(msg), properties=pika.BasicProperties(delivery_mode=2))
        conn.close()
        logger.info(f"[Node: Trigger, Job: {job_id}] Job successfully published.")
        state["error"] = None
    except Exception as e:
        state["error"] = f"Failed to publish to RabbitMQ. Error: {e}"
        logger.error(f"[Node: Trigger, Job: {job_id}] {state['error']}")
    return state

# NODE 4: Cleanup
def cleanup_node(state: IngestionState) -> IngestionState:
    if not state.get("temp_file_path"):
        return state
    job_id, temp_file_path = state["job_id"], state["temp_file_path"]
    logger.info(f"[Node: Cleanup, Job: {job_id}] Deleting temp file.")
    try:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
    except Exception as e:
        logger.warning(f"[Node: Cleanup, Job: {job_id}] Failed to delete temp file: {e}")
    return state