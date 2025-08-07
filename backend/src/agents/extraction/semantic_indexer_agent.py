import weaviate
import weaviate.classes as wvc
from sentence_transformers import SentenceTransformer
from typing import List

WEAVIATE_CLASS_NAME="FinancialDocumentChunk"

class SemanticIndexerAgent:
    def __init__(self):
        print("[IndexerAgent] Initializing...")
        
        self.weaviate_client = weaviate.connect_to_local(
            host="weaviate_db",
            port=8080,
            grpc_port=50051
        )
        print("[IndexerAgent] Connected to Weaviate")
        
        self.collection = self.weaviate_client.collections.get(WEAVIATE_CLASS_NAME)
        
        print("[IndexerAgent] Loading sentence-transformer model 'all-mpnet-base-v2'...")
        self.model = SentenceTransformer('all-mpnet-base-v2')
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"[IndexerAgent] Model Loaded. Embedding dimensions: {self.embedding_dim}.")
        
        self.create_schema_if_not_exists()
        print("[IndexerAgent] Initialization Complete.")
        
    def _create_schema_if_not_exists(self):
        if not self.weaviate_client.collections.exists(WEAVIATE_CLASS_NAME):
            print(f"[IndexerAgent] Collection {WEAVIATE_CLASS_NAME} doesn't exist. Creating now.")
            self.collection = self.weaviate_client.collections.create(
                name=WEAVIATE_CLASS_NAME,
                vector_config=wvc.config.Configure.Vectorizer.none(),
                properties=[
                    wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="source_s3_path", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="chunk_number", data_type=wvc.config.DataType.INT),
                ]
            )
            print(f"[IndexerAgent] Collection created.")
        else:
            print(f"[IndexerAgent] Collection '{WEAVIATE_CLASS_NAME}' already exists.")
    
    def run(self, text_chunks: List[str], s3_path: str) -> bool:
        if not text_chunks:
            print("[IndexerAgent] No text chunks to index. Skipping.")
            return False
        
        print(f"[IndexerAgent] Starting indexing for {len(text_chunks)} chunks from: {s3_path}")
        
        try:
            embeddings = self.model.encode(text_chunks, show_progress_bar=True)
            
            data_objects = []
            for i, chunk in enumerate(text_chunks):
                data_objects.append(
                    wvc.data.DataObject(
                        properties={
                            "text": chunk,
                            "source_s3_path": s3_path,
                            "chunk_number": i + 1,
                        },
                        vector=embeddings[i]
                    )
                )
            print(f"[IndexerAgent] Inserting {len(data_objects)} objects into Weaviate...")
            with self.collection.batch.dynamic() as batch:
                for obj in data_objects:
                    batch.add_object(
                        properties=obj.properties,
                        vector=obj.vector
                    )
            
            print("[IndexerAgent] Indexing complete.")
            return True
            
        except Exception as e:
            print(f"ERROR in IndexerAgent: {e}")
            self.weaviate_client.close()
            return False
    
    def close_connection(self):
        """Closes the connection to Weaviate."""
        self.weaviate_client.close()
        print("[IndexerAgent] Weaviate connection closed.")
