import json
import pika
from core.config import settings
from pipelines.extraction_graph import extraction_graph_app
from agents.extraction.parser_agent import ParserAgent
from agents.extraction.semantic_indexer_agent import SemanticIndexerAgent

# This is our pipeline orchestrator for the worker
# class Pipeline:
#     def __init__(self):
#         self.parser_agent = ParserAgent()
#         self.semantic_indexer_agent = SemanticIndexerAgent()
#         # self.kpi_agent = KPIExtractionAgent()

#     def run(self, s3_path: str):
#         # to run the extraction pipeline
#         print(f"\n--- Starting Pipeline for: {s3_path} ---")
        
#         # Step 1: Parse the document
#         text_chunks = self.parser_agent.parse_document(s3_path)
#         if not text_chunks:
#             print("[Pipeline] Parsing failed or returned no text. Halting processing.")
#             return

#         # Next steps will go here...
#         print(f"--- Pipeline Finished for: {s3_path} ---")


def main():
    print("--- Starting LangGraph-Based Background Worker ---")
    
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', credentials=credentials))
    channel = connection.channel()
    queue_name = 'doc_processing_queue'
    channel.queue_declare(queue=queue_name, durable=True)
    print(f"[*] Worker waiting for messages in queue '{queue_name}'.")

    def callback(ch, method, properties, body):
        print(f"\n[x] Worker received new message.")
        message_data = json.loads(body.decode())
        s3_path = message_data.get("s3_path")

        if s3_path:
            initial_state = {"s3_path": s3_path}
            
            print(f"--- Invoking Extraction Graph for: {s3_path} ---")
            final_state = extraction_graph_app.invoke(initial_state)
            
            print("--- Graph Execution Finished ---")
            print("Final State:")
            # We can inspect the final state to see what happened
            print(f"  - s3_path: {final_state.get('s3_path')}")
            print(f"  - Chunks found: {len(final_state.get('text_chunks', []))}")
            print(f"  - Indexing successful: {final_state.get('indexing_was_successful')}")

        else:
            print("[!] Message did not contain a valid 's3_path'. Discarding.")
        
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=queue_name, on_message_callback=callback)
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Worker crashed with error: {e}")