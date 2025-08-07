import boto3.session
import httpx 
import boto3
import io 
import os
import re
import pika
import json
import pika.spec
from fastapi import UploadFile, HTTPException, status
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from dotenv import load_dotenv
from core.config import settings


load_dotenv()

#T7.2 File url validation requirements
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_MIME_TYPES = ["application/pdf", "text/html"]

# ... source handler agent and methods ...
class SourceHandlerAgent:
    def __init__(self):
        #initializes the agent and setup the minIO S3 client
        self.minio_endpoint = settings.MINIO_ENDPOINT_URL
        self.minio_access_key = settings.MINIO_ROOT_USER
        self.minio_secret_key = settings.MINIO_ROOT_PASSWORD
        self.bucket_name = settings.S3_BUCKET_NAME
        
        if not all([self.minio_access_key, self.minio_secret_key, self.bucket_name]):
            raise ValueError("MINIO creds or bucket name ain't set in the .env file")
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url = self.minio_endpoint,
            aws_access_key_id=self.minio_access_key,
            aws_secret_access_key=self.minio_secret_key,
            config=boto3.session.Config(signature_version='s3v4')
        )
        self.create_bucket_if_not_exists()
        
    def create_bucket_if_not_exists(self):
        #checks if the bucket exists and if not then create one
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"Bucket '{self.bucket_name}' already exists.")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                print(f"Bucket '{self.bucket_name}' does not exist. Creating it now.")
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                raise
        
    def upload_file_to_storage(self, file:UploadFile, company_name: str = 'unknown', report_type: str = '10-k') -> str:
        try:
            object_name = f"raw_filings/{company_name.upper()}/{report_type.upper()}/{file.filename}"
            print(f"Uploading {file.filename} to MinIO bucket '{self.bucket_name}' as '{object_name}'")
            
            self.s3_client.upload_fileobj(
                file.file,        
                self.bucket_name, 
                object_name     
            )
            
            
            print("Upload successful.")
            return object_name
        
        except ClientError as e:
            print(f"ERROR: Failed to upload file to MinIO. {e}")
            return None # Return None to indicate failure
        except Exception as e:
            print(f"An unexpected error occurred during file upload: {e}")
            return None


    def validate_file(self, file: UploadFile):
        """
        Validates a direct file upload.
        """
        #Check MIME type (more reliable than filename extension)
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type: {file.content_type}. Only PDF and HTML are allowed."
            )
            
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File is too large. Maximum size is {MAX_FILE_SIZE_MB} MB."
            )
        
        print(f"File validation successful for {file.filename}.")
        
    async def handle_url(self, url: str) -> str:
        try:
            # httpx to download content from the URL ===
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                print(f"[Fetcher] Received URL: {url}. Starting download.")
                head_response = await client.get(url)
                head_response.raise_for_status()
                print("[Fetcher] Download successful.")

                 # (Optional but good) Validate the content type
                content_type = head_response.headers.get('content-type', '').lower()
                if 'pdf' not in content_type and 'html' not in content_type:
                    raise HTTPException(status_code=400, detail=f"Unsupported content type: {content_type}")
            
                content_length = int(head_response.headers.get('content-length', 0))
                if content_length > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail=f"File at URL is too large (> {MAX_FILE_SIZE_MB}MB).")
            
                filename = None
                if 'content-disposition' in head_response.headers:
                    # Use a regex to safely extract filename from the header
                    # e.g., Content-Disposition: attachment; filename="example.pdf"
                    cd_header = head_response.headers['content-disposition']
                    matches = re.findall(r'filename="?([^"]+)"?', cd_header)
                    if matches:
                        filename = matches[0]
                    
                if not filename:
                    final_url = str(head_response.url) # httpx gives the final URL after redirects
                    filename = os.path.basename(urlparse(final_url).path) or "downloaded_file"
                
                #let's say if the filename is still empty
                if not filename:
                    filename = "downloaded_document.pdf"
                
                print(f"[Fetcher] Determined final filename to be: {filename}")
            
                # Perform GET request to download content (using the SAME client)
                print(f"[Fetcher] Performing GET request to download content from: {head_response.url}")
                get_response = await client.get(head_response.url) # Use the final URL
                get_response.raise_for_status()
                
                content_bytes = await get_response.aread()
                file_like_object = io.BytesIO(content_bytes)

                temp_upload_file = UploadFile(filename=filename, file=file_like_object)
                self.validate_file(temp_upload_file)

                return self.upload_file_to_storage(file=temp_upload_file)

        except httpx.RequestError as e:
            # Handle download-specific errors
            raise HTTPException(status_code=400, detail=f"Failed to fetch file from URL: {e}")
        except HTTPException as e:
            # Handle our own validation errors
            raise e
        except Exception as e:
            print(f"An unexpected error occurred during URL handling: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while handling URL.")

    
    def publish_to_processing_queue(self, s3_path: str):
        #publish message to rabbitmq to trigger asynchronous processing pipeline
        try:
            rabbitmq_user = settings.RABBITMQ_USER
            rabbitmq_pass = settings.RABBITMQ_PASS
            credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
            
            #conntect to RabbitMQ that we pulled from docker compose
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host='rabbitmq', credentials=credentials)
            )
            channel = connection.channel()
            
            # this logic can survice rabbitmq restart :)
            queue_name = 'doc_processing_queue'
            channel.queue_declare(queue=queue_name, durable=True)
            
            message_body = json.dumps({"s3_path": s3_path})
            
            channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE # making it persistent
                )
            )
            
            print(f"[x] sent message to queue '{queue_name}': {message_body}")
            connection.close()
            
        except Exception as e:
            print(f"ERROR: failed to publish message to RabbitMQ. {e}")