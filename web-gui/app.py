# Azure Web GUI for A2A Translation Service

from flask import Flask, render_template, request, jsonify
import requests
import json
import os
import uuid
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Azure Configuration ---
AZURE_STORAGE_ACCOUNT_NAME = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME')
AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')
TRANSLATION_AGENT_URL = os.environ.get('TRANSLATION_AGENT_URL')

# Initialize Azure services with managed identity
credential = DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID)

def get_blob_service_client():
    """Get Azure Blob Service Client with managed identity authentication."""
    if not AZURE_STORAGE_ACCOUNT_NAME:
        raise ValueError("AZURE_STORAGE_ACCOUNT_NAME environment variable not set")
    
    account_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=credential)

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "web-gui"}), 200

@app.route('/agent-card')
def get_agent_card():
    """Returns the translation agent card with dynamic endpoints."""
    try:
        if not TRANSLATION_AGENT_URL:
            return jsonify({"error": "TRANSLATION_AGENT_URL not configured"}), 500
            
        agent_card = {
            "agent_id": "translation-agent-v1",
            "name": "Azure Asynchronous Text Translation Agent",
            "description": "An agent that receives text translation tasks asynchronously using Azure AI Translator, deployed on Azure Container Apps.",
            "skills": [
                {
                    "skill_name": "translate_text",
                    "endpoint": f"{TRANSLATION_AGENT_URL}/execute_task",
                    "status_endpoint": f"{TRANSLATION_AGENT_URL}/get_task_status",
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
        return jsonify(agent_card), 200
    except Exception as e:
        logger.error(f"Error generating agent card: {e}")
        return jsonify({"error": "Failed to generate agent card"}), 500

@app.route('/agent-card-file')
def get_agent_card_file():
    """Returns the agent card file content with updated endpoints."""
    try:
        # Try to read the updated file first
        try:
            with open('translation_agent_card.json', 'r') as f:
                agent_card = json.load(f)
            return jsonify(agent_card), 200
        except FileNotFoundError:
            # Fallback to dynamic generation
            return get_agent_card()
    except Exception as e:
        logger.error(f"Error reading agent card file: {e}")
        return jsonify({"error": "Failed to read agent card file"}), 500

@app.route('/upload-and-translate', methods=['POST'])
def upload_and_translate():
    """
    Receives a file, initiates an A2A task, and returns an immediate task ID.
    """
    try:
        # --- 1. Agent Discovery (from environment variable) ---
        logger.info("GUI Backend: Discovering translation agent...")
        if not TRANSLATION_AGENT_URL:
            raise ValueError("TRANSLATION_AGENT_URL environment variable not set")
            
        agent_endpoint = f"{TRANSLATION_AGENT_URL}/execute_task"
        logger.info(f"GUI Backend: Found agent at {agent_endpoint}")

        # --- 2. Task Initiation (from user file upload) ---
        if 'file' not in request.files:
            return jsonify({"error": "No file part in the request."}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file."}), 400
        
        target_language = request.form.get('language', 'el')
        
        # Read file content for the task payload
        file_content = file.read().decode('utf-8')
        
        # --- 3. A2A Communication (asynchronous) ---
        task_id = str(uuid.uuid4())
        task_payload = {
            "envelope": {
                "task_id": task_id,
                "target_language": target_language
            },
            "parts": {
                "document_content": file_content
            }
        }
        
        logger.info(f"GUI Backend: Sending task {task_id} to Translation Agent...")
        # Send task to translation agent
        response = requests.post(agent_endpoint, json=task_payload, timeout=30)
        response.raise_for_status()

        # The Translation Agent should return a 202 status and the task ID.
        if response.status_code == 202:
            # We don't have the result yet, just the task ID
            response_data = response.json()
            return jsonify({
                "task_id": response_data.get("task_id"),
                "message": "Task submitted. Polling for result...",
                "status": "pending"
            }), 200 # OK response with a pending status
        else:
            return jsonify({"error": "Agent did not accept the task as expected."}), 500

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return jsonify({"error": f"Configuration error: {e}"}), 500
    except requests.exceptions.RequestException as e:
        logger.error(f"Communication error with Translation Agent: {e}")
        return jsonify({"error": f"Communication error with Translation Agent: {e}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/get-task-status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    This endpoint checks Azure Blob Storage for completed translation results.
    """
    try:
        # Check Azure Blob Storage for results
        blob_service_client = get_blob_service_client()
        container_name = "translation-results"
        blob_name = f"{task_id}.json"
        
        try:
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            blob_data = blob_client.download_blob().readall()
            result_data = json.loads(blob_data.decode('utf-8'))
            logger.info(f"Found completed task result for {task_id}")
            return jsonify(result_data), 200
        except Exception as blob_error:
            # If blob doesn't exist, task is still pending
            logger.info(f"Task {task_id} still pending: {blob_error}")
            return jsonify({"status": "pending"}), 200
            
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # For Azure Container Apps, listen on all interfaces on port 5000
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"A2A Web GUI starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
