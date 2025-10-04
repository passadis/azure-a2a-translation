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

@app.route('/upload-and-translate', methods=['POST'])
def upload_and_translate():
    """Send A2A Protocol compliant message with fallback to legacy format"""
    try:
        # --- 1. Agent Discovery (from environment variable) ---
        logger.info("GUI Backend: Discovering translation agent...")
        if not TRANSLATION_AGENT_URL:
            raise ValueError("TRANSLATION_AGENT_URL environment variable not set")

        # --- 2. Task Initiation (from user file upload) ---
        if 'file' not in request.files:
            return jsonify({"error": "No file part in the request."}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file."}), 400
        
        target_language = request.form.get('language', 'el')
        file_content = file.read().decode('utf-8')
        
        # --- 3. Try A2A JSON-RPC 2.0 first ---
        try:
            logger.info("GUI Backend: Attempting A2A JSON-RPC 2.0 communication...")
            
            # Create A2A Message
            message = {
                "role": "user",
                "parts": [
                    {"kind": "text", "text": file_content},
                    {"kind": "data", "data": {"target_language": target_language}}
                ],
                "messageId": str(uuid.uuid4()),
                "kind": "message"
            }
            
            # Create JSON-RPC 2.0 request
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {"message": message},
                "id": str(uuid.uuid4())
            }
            
            # Send to A2A agent
            a2a_endpoint = f"{TRANSLATION_AGENT_URL}/"
            response = requests.post(
                a2a_endpoint,
                json=jsonrpc_request,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            
            jsonrpc_response = response.json()
            
            if "result" in jsonrpc_response:
                task = jsonrpc_response["result"]
                logger.info(f"A2A task {task['id']} submitted successfully")
                return jsonify({
                    "task_id": task["id"],
                    "status": task["status"]["state"],
                    "message": "A2A translation task submitted successfully",
                    "protocol": "A2A"
                }), 200
            else:
                error = jsonrpc_response.get("error", {})
                raise Exception(f"A2A error: {error.get('message', 'Unknown error')}")
                
        except Exception as a2a_error:
            logger.warning(f"A2A communication failed, falling back to legacy: {a2a_error}")
            
            # --- 4. Fallback to Legacy REST API ---
            logger.info("GUI Backend: Using legacy REST API...")
            
            task_id = str(uuid.uuid4())
            legacy_payload = {
                "envelope": {
                    "task_id": task_id,
                    "target_language": target_language
                },
                "parts": {
                    "document_content": file_content
                }
            }
            
            legacy_endpoint = f"{TRANSLATION_AGENT_URL}/execute_task"
            response = requests.post(legacy_endpoint, json=legacy_payload, timeout=30)
            response.raise_for_status()

            if response.status_code == 202:
                response_data = response.json()
                logger.info(f"Legacy task {task_id} submitted successfully")
                return jsonify({
                    "task_id": response_data.get("task_id", task_id),
                    "message": "Legacy translation task submitted successfully",
                    "status": "pending",
                    "protocol": "Legacy"
                }), 200
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
    """Check Azure Blob Storage for completed translation results (A2A and legacy)"""
    try:
        # Check Azure Blob Storage for results
        blob_service_client = get_blob_service_client()
        container_name = "translation-results"
        
        # Try A2A format first
        a2a_blob_name = f"{task_id}.json"
        try:
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=a2a_blob_name)
            blob_data = blob_client.download_blob().readall()
            result_data = json.loads(blob_data.decode('utf-8'))
            
            # Check if it's A2A format
            if result_data.get("kind") == "task":
                logger.info(f"Found A2A task result for {task_id}")
                # Extract artifact content for web GUI compatibility
                artifact_content = ""
                if result_data.get("artifacts"):
                    for artifact in result_data["artifacts"]:
                        for part in artifact.get("parts", []):
                            if part.get("kind") == "text":
                                artifact_content = part.get("text", "")
                                break
                        if artifact_content:
                            break
                
                return jsonify({
                    "task_id": task_id,
                    "status": "completed",
                    "artifact_content": artifact_content,
                    "processed_at": result_data["status"]["timestamp"],
                    "protocol": "A2A"
                }), 200
            else:
                # Legacy format
                logger.info(f"Found legacy task result for {task_id}")
                result_data["protocol"] = "Legacy"
                return jsonify(result_data), 200
                
        except Exception:
            # Try legacy format
            legacy_blob_name = f"{task_id}-legacy.json"
            try:
                blob_client = blob_service_client.get_blob_client(container=container_name, blob=legacy_blob_name)
                blob_data = blob_client.download_blob().readall()
                result_data = json.loads(blob_data.decode('utf-8'))
                logger.info(f"Found legacy task result for {task_id}")
                result_data["protocol"] = "Legacy"
                return jsonify(result_data), 200
            except Exception as legacy_error:
                # Task still pending
                logger.info(f"Task {task_id} still pending: {legacy_error}")
                return jsonify({
                    "task_id": task_id,
                    "status": "pending",
                    "message": "Task is being processed"
                }), 200
            
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/agent-discovery', methods=['GET'])
def agent_discovery():
    """Discover agent capabilities through A2A standard endpoint"""
    try:
        if not TRANSLATION_AGENT_URL:
            return jsonify({"error": "Translation agent URL not configured"}), 500
            
        # Try A2A discovery first
        try:
            a2a_discovery_url = f"{TRANSLATION_AGENT_URL}/.well-known/agent.json"
            response = requests.get(a2a_discovery_url, timeout=10)
            response.raise_for_status()
            
            agent_card = response.json()
            logger.info("Successfully discovered A2A agent capabilities")
            return jsonify({
                "protocol": "A2A",
                "agent_card": agent_card,
                "discovery_url": a2a_discovery_url
            }), 200
            
        except Exception as a2a_error:
            logger.warning(f"A2A discovery failed: {a2a_error}")
            
            # Fallback to legacy discovery
            try:
                legacy_discovery_url = f"{TRANSLATION_AGENT_URL}/agent-card"
                response = requests.get(legacy_discovery_url, timeout=10)
                response.raise_for_status()
                
                agent_card = response.json()
                logger.info("Successfully discovered legacy agent capabilities")
                return jsonify({
                    "protocol": "Legacy",
                    "agent_card": agent_card,
                    "discovery_url": legacy_discovery_url
                }), 200
                
            except Exception as legacy_error:
                logger.error(f"Legacy discovery also failed: {legacy_error}")
                return jsonify({
                    "error": "Could not discover agent capabilities",
                    "a2a_error": str(a2a_error),
                    "legacy_error": str(legacy_error)
                }), 503
                
    except Exception as e:
        logger.error(f"Agent discovery error: {e}")
        return jsonify({"error": f"Agent discovery failed: {e}"}), 500

if __name__ == '__main__':
    # For Azure Container Apps, listen on all interfaces on port 5000
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"A2A Web GUI starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
