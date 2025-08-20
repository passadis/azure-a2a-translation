import time
import json
import os
import uuid
import requests
import logging
from dotenv import load_dotenv
from azure.storage.queue import QueueServiceClient
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Azure Configuration ---
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_TRANSLATOR_ENDPOINT = os.getenv("AZURE_TRANSLATOR_ENDPOINT")
AZURE_TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION")
AZURE_TRANSLATOR_RESOURCE_ID = os.getenv("AZURE_TRANSLATOR_RESOURCE_ID")
TRANSLATION_JOBS_QUEUE = os.getenv("TRANSLATION_JOBS_QUEUE", "translation-jobs")
TRANSLATION_RESULTS_QUEUE = os.getenv("TRANSLATION_RESULTS_QUEUE", "translation-results")

# --- Queue Configuration ---
POLL_INTERVAL_SECONDS = 5  # How often the worker checks for new jobs
MESSAGE_VISIBILITY_TIMEOUT = 300  # 5 minutes to process a message

def get_queue_service_client():
    """Get authenticated queue service client using managed identity"""
    try:
        # Use DefaultAzureCredential which works with managed identity in Azure
        credential = DefaultAzureCredential()
        account_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.queue.core.windows.net"
        return QueueServiceClient(account_url=account_url, credential=credential)
    except Exception as e:
        logger.error(f"Failed to create queue service client: {e}")
        raise

def get_blob_service_client():
    """Get authenticated blob service client using managed identity"""
    try:
        # Use DefaultAzureCredential which works with managed identity in Azure
        credential = DefaultAzureCredential()
        account_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        return BlobServiceClient(account_url=account_url, credential=credential)
    except Exception as e:
        logger.error(f"Failed to create blob service client: {e}")
        raise

def translate_text_with_azure(text, target_language="el"):
    """
    Calls the Azure AI Translator service to translate text using managed identity.
    """
    if not all([AZURE_TRANSLATOR_ENDPOINT, AZURE_TRANSLATOR_REGION]):
        raise ValueError("Azure Translator configuration is incomplete.")

    try:
        # Use managed identity for authentication with Cognitive Services
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
        
        # Get access token for Cognitive Services
        token = credential.get_token("https://cognitiveservices.azure.com/.default")
        
        path = '/translate'
        constructed_url = AZURE_TRANSLATOR_ENDPOINT.rstrip('/') + path

        params = {
            'api-version': '3.0',
            'to': [target_language]
        }

        headers = {
            'Authorization': f'Bearer {token.token}',
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4()),
            'Ocp-Apim-ResourceId': AZURE_TRANSLATOR_RESOURCE_ID or '/subscriptions/9d47bf93-091d-480e-a512-1e918864fee7/resourceGroups/rg-sets/providers/Microsoft.CognitiveServices/accounts/cog-sets',
            'Ocp-Apim-Subscription-Region': AZURE_TRANSLATOR_REGION
        }

        body = [{'text': text}]

        logger.info("Sending request to Azure AI Translator...")
        translator_request = requests.post(constructed_url, params=params, headers=headers, json=body)
        translator_request.raise_for_status()
        translator_response = translator_request.json()
        
        return translator_response[0]['translations'][0]['text']
        
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise

def process_queue_message(queue_client, message):
    """
    Process a single message from the queue.
    """
    try:
        # Parse the message content
        task_data = json.loads(message.content)
        task_id = task_data["task_id"]
        document_content = task_data["document_content"]
        target_language = task_data["target_language"]
        
        logger.info(f"Processing task {task_id}...")
        
        # Translate the text
        translated_text = translate_text_with_azure(document_content, target_language)
        
        # Prepare result
        result_payload = {
            "task_id": task_id,
            "status": "completed",
            "artifact_content": translated_text,
            "processed_at": time.time()
        }
        
        # Save result to blob storage
        blob_service_client = get_blob_service_client()
        container_name = "translation-results"
        blob_name = f"{task_id}.json"
        try:
            blob_service_client.create_container(container_name)
        except ResourceExistsError:
            pass
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        result_json = json.dumps(result_payload, indent=2)
        blob_client.upload_blob(result_json, overwrite=True)

        # Send result to translation-results queue
        queue_service_client = get_queue_service_client()
        results_queue_client = queue_service_client.get_queue_client(TRANSLATION_RESULTS_QUEUE)
        try:
            results_queue_client.create_queue()
        except ResourceExistsError:
            pass
        results_queue_client.send_message(result_json)

        # Delete the processed message from the jobs queue
        queue_client.delete_message(message.id, message.pop_receipt)

        logger.info(f"Task {task_id} completed successfully, saved to blob storage, and sent to results queue")
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid message format: {e}")
        # Delete malformed message
        queue_client.delete_message(message.id, message.pop_receipt)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        # Message will become visible again after visibility timeout
        # In a production system, you might want to implement dead letter queue logic

def ensure_queue_exists(queue_service_client, queue_name):
    """
    Ensure that a queue exists, create it if it doesn't.
    """
    try:
        queue_client = queue_service_client.get_queue_client(queue_name)
        queue_client.create_queue()
        logger.info(f"Queue '{queue_name}' created successfully")
        return True
    except ResourceExistsError:
        logger.info(f"Queue '{queue_name}' already exists")
        return True
    except Exception as e:
        logger.error(f"Failed to create queue '{queue_name}': {e}")
        return False

def start_worker():
    """
    Main worker loop that processes messages from Azure Storage Queue.
    """
    logger.info("--- Translation Worker is starting ---")
    logger.info(f"Monitoring queue: {TRANSLATION_JOBS_QUEUE}")
    logger.info("Results will be saved to blob storage")
    
    try:
        # Initialize queue clients
        queue_service_client = get_queue_service_client()
        
        # Ensure jobs queue exists before starting to process
        logger.info("Ensuring required queue exists...")
        if not ensure_queue_exists(queue_service_client, TRANSLATION_JOBS_QUEUE):
            logger.error(f"Failed to ensure queue exists: {TRANSLATION_JOBS_QUEUE}")
            return
            
        jobs_queue_client = queue_service_client.get_queue_client(TRANSLATION_JOBS_QUEUE)
        
        # Log queue statistics
        try:
            queue_properties = jobs_queue_client.get_queue_properties()
            logger.info(f"Queue properties - Approximate message count: {queue_properties.approximate_message_count}")
        except Exception as e:
            logger.warning(f"Could not get queue properties: {e}")
        
        logger.info("Successfully connected to Azure Storage Queue")
            
    except Exception as e:
        logger.error(f"Failed to initialize queue client: {e}")
        return
    
    # Main processing loop
    while True:
        try:
            # Receive messages from the jobs queue
            logger.info(f"Polling queue '{TRANSLATION_JOBS_QUEUE}' for messages...")
            messages = jobs_queue_client.receive_messages(
                messages_per_page=1,
                visibility_timeout=MESSAGE_VISIBILITY_TIMEOUT
            )
            
            message_processed = False
            message_count = 0
            for message in messages:
                message_count += 1
                logger.info(f"Found message {message_count}: ID={message.id}, Content preview: {message.content[:100]}...")
                process_queue_message(jobs_queue_client, message)
                message_processed = True
                break  # Process one message at a time
            
            if not message_processed:
                # No messages available, wait before next poll
                logger.info(f"No messages found in queue. Waiting {POLL_INTERVAL_SECONDS} seconds...")
                time.sleep(POLL_INTERVAL_SECONDS)
            else:
                logger.info(f"Processed {message_count} message(s). Continuing immediately...")
                
        except KeyboardInterrupt:
            logger.info("Worker stopped by user.")
            break
        except Exception as e:
            logger.error(f"An error occurred in the worker loop: {e}")
            time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == '__main__':
    start_worker()
