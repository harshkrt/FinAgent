import boto3.session
import httpx 
import boto3
import io 
import os
import pika
import json
import pika.spec
from fastapi import UploadFile, HTTPException
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# ... source handler agent and methods ...
class SourceHandlerAgent:
    def __init__(self):
        #initializes the agent and setup the minIO S3 client
        self.minio_endpoint = "http://minio:9000"
        self.minio_access_key = os.getenv("MINIO_ROOT_USER")
        self.minio_secret_key = os.getenv("MINIO_ROOT_PASSWORD")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        
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
                file.file,        # The file-like object from the UploadFile
                self.bucket_name, # The target bucket
                object_name       # The desired path/name within the bucket
            )
            
            
            print("Upload successful.")
            return object_name
        
        except ClientError as e:
            print(f"ERROR: Failed to upload file to MinIO. {e}")
            return None # Return None to indicate failure
        except Exception as e:
            print(f"An unexpected error occurred during file upload: {e}")
            return None


        
        
    async def handle_url(self, url:str) -> str:
        #fetches document from a url, validates it and uploads it to MinIO
    
        try:
            async with httpx.AsyncClient() as client:
                response = client.get(url, follow_redirects=True, timeout=30.0)
                response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and 'html' not in content_type:
                raise HTTPException(status_code=400, detail=f"unsupported content type: {content_type}")
        
            content_bytes = await response.aread()
            file_like_object = io.BytesIO(content_bytes)
        
            #extract file name from url
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename:
                filename = "downloaded_file.pdf" # fallback filename
            
            temp_upload_file = UploadFile(filename=filename, file=file_like_object)
            s3_path = self.upload_file_to_storage(file=temp_upload_file)
        
            return s3_path
    
        except httpx.RequestError as e:
            raise HTTPException(status_code=400, detail=f"failed to fetch file from the url: {e}")
        except HTTPException as e:
            raise e # re-raise from validation
    
        except Exception as e:
            print(f"Unexpected error occured during URL handling: {e}")
            raise HTTPException(status_code=400, detail="internal server error while handling URL.")

    
    def publish_to_processing_queue(self, s3_path: str):
        #publish message to rabbitmq to trigger asynchronous processing pipeline
        try:
            rabbitmq_user = os.getenv("RABBITMQ_USER")
            rabbitmq_pass = os.getenv("RABBITMQ_PASS")
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