from agents.extraction.parser_agent import ParserAgent
from agents.extraction.semantic_indexer_agent import SemanticIndexerAgent
from typing import List, TypedDict
from langgraph.graph import StateGraph, END

class ExtractionGraphState(TypedDict):
    s3_path: str
    text_chunks: List[str]
    indexing_was_successful: bool


def parse_document_node(state: ExtractionGraphState) -> dict:
    print("--- 1. PARSE DOCUMENT NODE ---")
    s3_path = state.get("s3_path")
    if not s3_path:
        raise ValueError("s3_path not found in state.")
    
    parser_agent = ParserAgent()
    text_chunks = parser_agent.parse_document(s3_path)
    
    return {"text_chunks": text_chunks}

def index_document_node(state: ExtractionGraphState) -> dict:
    print("--- 2. INDEX DOCUMENT NODE ---")
    text_chunks = state.get("text_chunks")
    s3_path = state.get("s3_path")

    if not text_chunks:
        print("No text chunks to index. Skipping.")
        return {"indexing_was_successful": False}
    
    indexer_agent = SemanticIndexerAgent()
    was_successful = indexer_agent.run(text_chunks, s3_path)

    return {"indexing_was_successful": was_successful}

#TODO more nodes for other agents






def build_extraction_graph() -> StateGraph:
    workflow = StateGraph(ExtractionGraphState)
    
    workflow.add_node("parser", parse_document_node)
    workflow.add_node("indexer", index_document_node)
    
    workflow.set_entry_point("parser")
    workflow.add_edge("parser", "indexer")
    workflow.add_edge("indexer", END)
    
    app = workflow.compile()
    print("Extraction Graph built successfully.")
    return app

extraction_graph_app = build_extraction_graph()

    