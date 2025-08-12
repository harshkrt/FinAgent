from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any

class Settings(BaseSettings):
    # This tells Pydantic to load variables from the .env file
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding='utf-8')

    # --- PostgreSQL Settings ---
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    # This will be constructed automatically, not read from the .env file
    DATABASE_URL: str = "" 

    # --- RabbitMQ Settings ---
    RABBITMQ_USER: str
    RABBITMQ_PASS: str
    
    # --- MinIO Settings ---
    MINIO_HOST: str
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    S3_BUCKET_NAME: str

    # --- Neo4j Settings ---
    NEO4J_USER: str
    NEO4J_PASSWORD: str

    @model_validator(mode='before')
    def assemble_db_connection(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        This is a smart validator that runs before the model is created.
        It takes the individual Postgres variables and builds the full
        DATABASE_URL connection string, which SQLAlchemy needs.
        """
        # Get the individual parts from the environment variables
        user = values.get('POSTGRES_USER')
        password = values.get('POSTGRES_PASSWORD')
        db_name = values.get('POSTGRES_DB')
        
        # The hostname 'postgres_db' comes from the service name in your docker-compose.yml
        hostname = 'postgres_db'
        port = 5432
        
        # Assemble the full URL
        # Format: postgresql+<driver>://<user>:<password>@<host>:<port>/<db_name>
        values['DATABASE_URL'] = f"postgresql+psycopg2://{user}:{password}@{hostname}:{port}/{db_name}"
        
        return values

# Create a single, global instance of the settings to be used throughout the app
settings = Settings()