from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # This tells Pydantic to load variables from the .env file
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')


    # all our environment variables here
    # PostgreSQL
    POSTGRES_USER:str
    POSTGRES_PASSWORD:str
    POSTGRES_DB:str

    # Neo4j
    NEO4J_USER:str
    NEO4J_PASSWORD:str

    # RabbitMQ
    RABBITMQ_USER:str
    RABBITMQ_PASS:str

    # MinIO
    MINIO_ROOT_USER:str
    MINIO_ROOT_PASSWORD:str
    S3_BUCKET_NAME:str
    
    # You can add default values for things that might not be in the .env
    MINIO_ENDPOINT_URL: str = "http://minio:9000"

# Create a single, importable instance of the settings
settings = Settings()