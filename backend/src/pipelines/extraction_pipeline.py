from langgraph.graph import StateGraph, END
from typing import TypedDict, List
# --- Imports for the INGESTION TRIGGER pipeline ---
from src.agents.extraction.source_handler_agent import (
    IngestionState, 
    fetcher_node, 
    archiver_node, 
    trigger_node, 
    cleanup_node
)
# --- Imports for the DOCUMENT PROCESSING pipeline ---
from src.agents.extraction.parser_agent import (
    downloader_node,
    parser_node,
    log_parser_output_node,
    processing_cleanup_node
)
# --- NEW IMPORTS for AI processing steps ---
from src.agents.extraction.indexer_agent import (
    vectorizer_node, indexer_node
)


# ================================================================
# ==  PIPELINE 1: Document Ingestion Trigger
# ==  (Triggered by the API endpoint)
# ================================================================

def should_continue(state: dict):
    return "end_with_error" if state.get("error") else "continue"

ingestion_workflow = StateGraph(IngestionState)
ingestion_workflow.add_node("fetcher", fetcher_node)
ingestion_workflow.add_node("archiver", archiver_node)
ingestion_workflow.add_node("trigger", trigger_node)
ingestion_workflow.add_node("cleanup", cleanup_node)

ingestion_workflow.set_entry_point("fetcher")
ingestion_workflow.add_conditional_edges("fetcher", should_continue, {"continue": "archiver", "end_with_error": "cleanup"})
ingestion_workflow.add_conditional_edges("archiver", should_continue, {"continue": "trigger", "end_with_error": "cleanup"})
ingestion_workflow.add_conditional_edges("trigger", should_continue, {"continue": "cleanup", "end_with_error": "cleanup"})
ingestion_workflow.add_edge("cleanup", END)

ingestion_trigger_app = ingestion_workflow.compile()

# ================================================================
# ==  PIPELINE 2: Document Content Processing
# ==  (Triggered by the RabbitMQ worker)
# ================================================================

class ProcessingState(TypedDict):
    job_id: str
    s3_path: str
    local_path: str
    parsed_chunks: List[dict]
    error: str

# --- UPDATE THE GRAPH DEFINITION ---
processing_workflow = StateGraph(ProcessingState)

# Add the original nodes
processing_workflow.add_node("downloader", downloader_node)
processing_workflow.add_node("parser", parser_node)
# Add the NEW AI nodes
processing_workflow.add_node("vectorizer", vectorizer_node)
processing_workflow.add_node("indexer", indexer_node)
# Add the cleanup node
processing_workflow.add_node("processing_cleanup", processing_cleanup_node)

# Define the new, longer workflow
processing_workflow.set_entry_point("downloader")
processing_workflow.add_conditional_edges("downloader", should_continue, {"continue": "parser", "end_with_error": "processing_cleanup"})
processing_workflow.add_conditional_edges("parser", should_continue, {"continue": "vectorizer", "end_with_error": "processing_cleanup"})
processing_workflow.add_conditional_edges("vectorizer", should_continue, {"continue": "indexer", "end_with_error": "processing_cleanup"})
processing_workflow.add_conditional_edges("indexer", should_continue, {"continue": "processing_cleanup", "end_with_error": "processing_cleanup"})
processing_workflow.add_edge("processing_cleanup", END)
# This is the app our worker will call
processing_app = processing_workflow.compile()