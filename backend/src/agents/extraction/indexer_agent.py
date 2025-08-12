import logging
import weaviate

# THE FIX IS HERE: We need to import 'Property' from the 'config' sub-module
from weaviate.classes.config import Property 

from langchain_community.embeddings import OllamaEmbeddings
from ...core.config import settings

logger = logging.getLogger(__name__)

# NODE 1: Vectorizer (No changes needed here)
def vectorizer_node(state: dict) -> dict:
    if state.get("error"): return state
    job_id = state["job_id"]
    chunks = state.get("parsed_chunks", [])
    logger.info(f"[Node: Vectorizer, Job: {job_id}] Starting vectorization for {len(chunks)} chunks.")
    
    if not chunks:
        logger.warning(f"[Node: Vectorizer, Job: {job_id}] No chunks to vectorize.")
        return state

    try:
        ollama_embeddings = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url="http://ollama_service:11434"
        )
        texts_to_embed = [chunk["text"] for chunk in chunks]
        vectors = ollama_embeddings.embed_documents(texts_to_embed)
        
        for i, chunk in enumerate(chunks):
            chunk["vector"] = vectors[i]
            
        logger.info(f"[Node: Vectorizer, Job: {job_id}] Successfully generated embeddings.")
        state["parsed_chunks"] = chunks
        state["error"] = None
    except Exception as e:
        error_message = f"Failed to vectorize chunks. Error: {e}"
        logger.error(f"[Node: Vectorizer, Job: {job_id}] {error_message}")
        state["error"] = error_message

    return state

# NODE 2: Indexer (UPDATED WITH THE FIX)
def indexer_node(state: dict) -> dict:
    if state.get("error"): return state
    job_id = state["job_id"]
    enriched_chunks = state.get("parsed_chunks", [])
    logger.info(f"[Node: Indexer, Job: {job_id}] Starting indexing for {len(enriched_chunks)} chunks.")

    if not enriched_chunks:
        logger.warning(f"[Node: Indexer, Job: {job_id}] No chunks to index.")
        return state
        
    try:
        client = weaviate.connect_to_local(
            host="weaviate_db",
            port=8080
        )

        collection_name = "FinancialDocumentChunk"
        
        if not client.collections.exists(collection_name):
            logger.info(f"Weaviate collection '{collection_name}' not found. Creating it.")
            client.collections.create(
                name=collection_name,
                properties=[
                    # THE FIX IS HERE: Use the correctly imported 'Property' class
                    Property(name="job_id", data_type=weaviate.classes.config.DataType.TEXT),
                    Property(name="source", data_type=weaviate.classes.config.DataType.TEXT),
                    Property(name="page_number", data_type=weaviate.classes.config.DataType.INT),
                    Property(name="text", data_type=weaviate.classes.config.DataType.TEXT),
                ]
            )

        doc_chunks = client.collections.get(collection_name)
        
        with doc_chunks.batch.dynamic() as batch:
            for chunk in enriched_chunks:
                properties = {
                    "job_id": job_id,
                    "source": chunk["source"],
                    "page_number": chunk["page_number"],
                    "text": chunk["text"],
                }
                batch.add_object(
                    properties=properties,
                    vector=chunk["vector"]
                )
        
        logger.info(f"[Node: Indexer, Job: {job_id}] Successfully indexed {len(enriched_chunks)} chunks.")
        state["error"] = None
        client.close()
    except Exception as e:
        error_message = f"Failed to index chunks in Weaviate. Error: {e}"
        logger.error(f"[Node: Indexer, Job: {job_id}] {error_message}")
        state["error"] = error_message

    return state