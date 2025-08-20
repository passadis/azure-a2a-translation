from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import uuid
import json
from azure.storage.queue import QueueServiceClient
from azure.identity import DefaultAzureCredential
import logging

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Azure Storage Queue Configuration ---
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
TRANSLATION_JOBS_QUEUE = os.getenv("TRANSLATION_JOBS_QUEUE", "translation-jobs")

# Initialize Azure Storage Queue client with Managed Identity
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

def ensure_queue_exists(queue_name):
    """Ensure the queue exists, create if it doesn't"""
    try:
        queue_service_client = get_queue_service_client()
        queue_client = queue_service_client.get_queue_client(queue_name)
        # Try to get queue properties, if it fails, create the queue
        try:
            queue_client.get_queue_properties()
            logger.info(f"Queue {queue_name} already exists")
        except Exception:
            # Queue doesn't exist, create it
            queue_client.create_queue()
            logger.info(f"Created queue {queue_name}")
        return queue_client
    except Exception as e:
        logger.error(f"Failed to ensure queue {queue_name} exists: {e}")
        raise

@app.route('/execute_task', methods=['POST'])
def execute_task():
    """
    Receives a task, sends it to Azure Storage Queue, and returns an immediate status update.
    This is the non-blocking A2A-compliant endpoint.
    """
    try:
        data = request.json
        # A2A Task Format: `envelope` and `parts` are typical.
        document_content = data.get("parts", {}).get("document_content")
        target_language = data.get("envelope", {}).get("target_language", "el")
        task_id = data.get("envelope", {}).get("task_id", str(uuid.uuid4()))

        if not document_content:
            return jsonify({"status": "failed", "error": "document_content is required"}), 400

        logger.info(f"Received A2A task {task_id}. Adding to Azure Storage Queue...")

        # --- NON-BLOCKING: Send the task to Azure Storage Queue ---
        try:
            queue_client = ensure_queue_exists(TRANSLATION_JOBS_QUEUE)
            
            # Prepare task payload for the queue
            task_payload = {
                "task_id": task_id,
                "document_content": document_content,
                "target_language": target_language
            }
            
            # Send message to queue
            message_content = json.dumps(task_payload)
            queue_client.send_message(message_content)
            
            logger.info(f"Task {task_id} successfully queued")
            
        except Exception as e:
            logger.error(f"Failed to queue task {task_id}: {e}")
            return jsonify({"error": f"Failed to queue task: {str(e)}", "status": "failed"}), 500

        # --- A2A Protocol Response ---
        # Respond immediately, confirming receipt of the task.
        response_payload = {
            "task_id": task_id,
            "status": "pending",
            "message": "Task received. A worker will process it shortly."
        }

        return jsonify(response_payload), 202 # 202 Accepted status

    except Exception as e:
        logger.error(f"ERROR: An error occurred: {e}")
        return jsonify({"error": str(e), "status": "failed"}), 500


@app.route('/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    Check the status of a translation task by looking for results.
    """
    try:
        # In a real implementation, you might check a results queue or database
        # For now, we'll return a simple status
        return jsonify({
            "task_id": task_id,
            "status": "processing",
            "message": "Task is being processed by a worker"
        })
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        return jsonify({"error": str(e), "status": "failed"}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for container apps"""
    try:
        # Test queue connection and ensure it exists
        queue_client = ensure_queue_exists(TRANSLATION_JOBS_QUEUE)
        queue_client.get_queue_properties()
        
        return jsonify({"status": "healthy", "message": "Service is running and queue is accessible"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route('/agent-card', methods=['GET'])
def get_agent_card():
    """
    Discovery endpoint - returns the agent's capabilities and endpoints.
    This allows other services to discover how to interact with this agent.
    """
    try:
        # Get the current host URL (this agent's URL)
        # In Container Apps, we can get this from environment or construct it
        agent_url = request.url_root.rstrip('/')
        
        agent_card = {
            "agent_id": "translation-agent-v1",
            "name": "Azure Asynchronous Text Translation Agent",
            "description": "An agent that receives text translation tasks asynchronously using Azure AI Translator, deployed on Azure Container Apps.",
            "skills": [
                {
                    "skill_name": "translate_text",
                    "endpoint": f"{agent_url}/execute_task",
                    "status_endpoint": f"{agent_url}/task_status",
                    "input_format": {
                        "type": "object",
                        "properties": {
                            "envelope": {
                                "type": "object",
                                "properties": {
                                    "task_id": {"type": "string"},
                                    "target_language": {"type": "string", "example": "el"}
                                }
                            },
                            "parts": {
                                "type": "object",
                                "properties": {
                                    "document_content": {"type": "string"}
                                }
                            }
                        }
                    },
                    "output_format": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["pending", "completed", "failed"]},
                            "artifact": {
                                "type": "object",
                                "properties": {
                                    "artifact_content": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            ]
        }
        
        logger.info(f"Agent card requested, returning endpoints for: {agent_url}")
        return jsonify(agent_card), 200
        
    except Exception as e:
        logger.error(f"Error generating agent card: {e}")
        return jsonify({"error": "Failed to generate agent card"}), 500


@app.route('/')
def index():
    """
    Simple status page for the agent.
    """
    return "<h1>Translation Agent (Producer) is active.</h1><p>It's ready to accept A2A translation tasks.</p>"


if __name__ == '__main__':
    logger.info("Translation Agent (A2A-evolved Producer) is starting on http://0.0.0.0:5000")
    # This app's only job is to receive and queue tasks.
    # The actual translation is done by a separate worker.
    app.run(host='0.0.0.0', port=5000, debug=False)
