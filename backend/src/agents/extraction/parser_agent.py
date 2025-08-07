import boto3
from pathlib import Path
import fitz  # This is the import for PyMuPDF

from core.config import settings

class ParserAgent:
    def __init__(self):
        """
        Initializes the ParserAgent with a MinIO client. No complex models to load.
        """
        print("[ParserAgent] Initializing...")
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.MINIO_ENDPOINT_URL,
            aws_access_key_id=settings.MINIO_ROOT_USER,
            aws_secret_access_key=settings.MINIO_ROOT_PASSWORD
        )
        self.bucket_name = settings.S3_BUCKET_NAME
        print("[ParserAgent] Initialization complete.")

    def _download_from_s3(self, s3_path: str) -> bytes:
        """Downloads a file's content from MinIO directly into memory as bytes."""
        try:
            print(f"[ParserAgent] Downloading {s3_path} from MinIO into memory...")
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_path)
            # Read the content of the file directly from the response
            file_bytes = response['Body'].read()
            print("[ParserAgent] Download complete.")
            return file_bytes
        except Exception as e:
            print(f"Error downloading {s3_path} from MinIO: {e}")
            raise

    def parse_document(self, s3_path: str) -> list[str]:
        """
        Main method: downloads a PDF from S3 and uses PyMuPDF to parse it.
        Returns a list of strings, where each string is the text content of a page.
        """
        try:
            # 1. Download the file content into a bytes object
            pdf_bytes = self._download_from_s3(s3_path)
            
            # 2. Open the PDF from the in-memory bytes
            # This is more efficient than saving to a temp file
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            print(f"[ParserAgent] PyMuPDF parsing document with {document.page_count} pages.")
            
            page_texts = []
            for page_num in range(document.page_count):
                page = document.load_page(page_num)
                text = page.get_text()
                page_texts.append(text)
            
            document.close()

            print(f"[ParserAgent] PyMuPDF parsing complete.")
            
            if page_texts:
                print("--- Page 1 Preview ---")
                print(page_texts[0][:500].strip() + "...")
                print("----------------------")
            
            return page_texts

        except Exception as e:
            print(f"ERROR in ParserAgent during parsing: {e}")
            return []