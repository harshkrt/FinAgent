import pika
import json
import logging
import time
import sys
import os

# Ensure the app can find its modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pipelines.extraction_pipeline import processing_app
from src.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Worker")

def connect_to_rabbitmq():
    """
    Connects to RabbitMQ with a retry mechanism.
    """
    max_retries = 10
    retry_delay = 5  # seconds
    retries = 0

    while retries < max_retries:
        try:
            logger.info(f"Attempting to connect to RabbitMQ (Attempt {retries + 1}/{max_retries})...")
            credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
            connection_params = pika.ConnectionParameters(
                host='rabbitmq_broker', 
                credentials=credentials, 
                heartbeat=600,
                blocked_connection_timeout=300
            )
            connection = pika.BlockingConnection(connection_params)
            logger.info("Successfully connected to RabbitMQ.")
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            logger.warning(f"RabbitMQ connection failed: {e}. Retrying in {retry_delay} seconds...")
            retries += 1
            time.sleep(retry_delay)
    
    logger.critical("Could not connect to RabbitMQ after several retries. Exiting.")
    return None

def main():
    connection = connect_to_rabbitmq()
    if not connection:
        sys.exit(1) # Exit with an error code if connection failed

    channel = connection.channel()

    queue_name = "document_processing_queue"
    channel.queue_declare(queue=queue_name, durable=True)
    logger.info('Worker is waiting for messages. To exit press CTRL+C')

    def callback(ch, method, properties, body):
        logger.info(f"Received message from queue.")
        message_data = json.loads(body)
        
        initial_state = {
            "job_id": message_data.get("job_id"),
            "s3_path": message_data.get("s3_path")
        }

        logger.info(f"Invoking processing pipeline for job {initial_state['job_id']}.")
        final_state = processing_app.invoke(initial_state)

        if final_state.get("error"):
            logger.error(f"Processing failed for job {initial_state['job_id']}. Error: {final_state['error']}")
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        else:
            logger.info(f"Successfully processed job {initial_state['job_id']}. Acknowledging message.")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=queue_name, on_message_callback=callback)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Worker shutting down.")
        connection.close()

if __name__ == '__main__':
    main()