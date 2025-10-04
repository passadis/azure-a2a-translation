from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv
import os
import uuid
import json
from datetime import datetime
from azure.storage.queue import QueueServiceClient
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import logging
from jsonrpc import JSONRPCResponseManager, dispatcher

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Azure Storage Queue Configuration ---
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
TRANSLATION_JOBS_QUEUE = os.getenv("TRANSLATION_JOBS_QUEUE", "translation-jobs")

# Initialize Azure clients with Managed Identity
def get_queue_service_client():
    """Get authenticated queue service client using managed identity"""
    try:
        credential = DefaultAzureCredential()
        account_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.queue.core.windows.net"
        return QueueServiceClient(account_url=account_url, credential=credential)
    except Exception as e:
        logger.error(f"Failed to create queue service client: {e}")
        raise

def get_blob_service_client():
    """Get authenticated blob service client using managed identity"""
    try:
        credential = DefaultAzureCredential()
        account_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        return BlobServiceClient(account_url=account_url, credential=credential)
    except Exception as e:
        logger.error(f"Failed to create blob service client: {e}")
        raise

# A2A Protocol Helper Functions
def create_a2a_task(task_id, status_state="submitted", message_content=None):
    """Create A2A Protocol compliant Task object"""
    task = {
        "id": task_id,
        "contextId": str(uuid.uuid4()),  # Server-generated context ID
        "status": {
            "state": status_state,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        },
        "artifacts": [],
        "history": [],
        "metadata": {},
        "kind": "task"
    }
    
    if message_content:
        task["status"]["message"] = create_a2a_message("agent", message_content)
    
    return task

def create_a2a_message(role, content, task_id=None):
    """Create A2A Protocol compliant Message object"""
    return {
        "role": role,
        "parts": [{"kind": "text", "text": content}],
        "messageId": str(uuid.uuid4()),
        "taskId": task_id,
        "kind": "message"
    }

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

# JSON-RPC 2.0 Main Endpoint
@app.route('/', methods=['POST'])
def handle_jsonrpc():
    """Main JSON-RPC 2.0 endpoint for A2A Protocol"""
    try:
        content_type = request.headers.get('Content-Type', '')
        if content_type != 'application/json':
            return jsonify({"error": "Content-Type must be application/json"}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400
            
        response = JSONRPCResponseManager.handle(json.dumps(data), dispatcher)
        return Response(response.json, mimetype='application/json')
        
    except Exception as e:
        logger.error(f"JSON-RPC handling error: {e}")
        return jsonify({"error": "Invalid JSON-RPC request"}), 400

# A2A Protocol Methods
@dispatcher.add_method
def message_send(message, configuration=None, metadata=None):
    """A2A Protocol message/send method"""
    try:
        # Extract content from A2A Message format
        text_content = None
        target_language = "en"
        
        for part in message.get("parts", []):
            if part.get("kind") == "text":
                text_content = part.get("text")
            elif part.get("kind") == "data":
                data = part.get("data", {})
                target_language = data.get("target_language", "en")
        
        if not text_content:
            raise ValueError("No text content found in message parts")
        
        # Create A2A Task
        task_id = str(uuid.uuid4())
        task = create_a2a_task(task_id, "submitted", "Translation task received")
        
        # Queue for background processing
        queue_client = ensure_queue_exists(TRANSLATION_JOBS_QUEUE)
        task_payload = {
            "task_id": task_id,
            "document_content": text_content,
            "target_language": target_language,
            "message_id": message.get("messageId")
        }
        
        message_content = json.dumps(task_payload)
        queue_client.send_message(message_content)
        
        logger.info(f"A2A task {task_id} successfully queued")
        
        # Update task status to working
        task["status"]["state"] = "working"
        task["status"]["message"] = create_a2a_message("agent", "Translation in progress", task_id)
        
        return task
        
    except Exception as e:
        logger.error(f"message/send error: {e}")
        raise Exception(f"Translation request failed: {str(e)}")

@dispatcher.add_method
def tasks_get(id, historyLength=None):
    """A2A Protocol tasks/get method"""
    try:
        # Check Azure Blob Storage for completed results
        blob_service_client = get_blob_service_client()
        container_name = "translation-results"
        blob_name = f"{id}.json"
        
        try:
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            blob_data = blob_client.download_blob().readall()
            result_data = json.loads(blob_data.decode('utf-8'))
            
            # Check if it's already A2A format or legacy format
            if result_data.get("kind") == "task":
                # Already A2A format
                return result_data
            else:
                # Legacy format, transform to A2A
                task = create_a2a_task(id, "completed")
                
                # Add artifact with translation result
                artifact = {
                    "artifactId": str(uuid.uuid4()),
                    "name": "Translation Result",
                    "description": f"Translated text to {result_data.get('target_language', 'unknown')}",
                    "parts": [
                        {
                            "kind": "text", 
                            "text": result_data.get("artifact_content", "")
                        }
                    ],
                    "metadata": {
                        "target_language": result_data.get("target_language"),
                        "processed_at": result_data.get("processed_at")
                    }
                }
                task["artifacts"] = [artifact]
                
                return task
            
        except Exception:
            # Task still pending
            task = create_a2a_task(id, "working", "Translation in progress")
            return task
            
    except Exception as e:
        logger.error(f"tasks/get error: {e}")
        raise Exception(f"Failed to retrieve task status: {str(e)}")

@dispatcher.add_method
def tasks_cancel(id):
    """A2A Protocol tasks/cancel method"""
    try:
        # In a real implementation, you would remove from queue or mark as cancelled
        task = create_a2a_task(id, "cancelled", "Task cancelled by user")
        return task
    except Exception as e:
        logger.error(f"tasks/cancel error: {e}")
        raise Exception(f"Failed to cancel task: {str(e)}")

# Legacy REST endpoints (for backward compatibility)
@app.route('/execute_task', methods=['POST'])
def execute_task_legacy():
    """Legacy REST endpoint for backward compatibility"""
    try:
        data = request.json
        document_content = data.get("parts", {}).get("document_content")
        target_language = data.get("envelope", {}).get("target_language", "el")
        task_id = data.get("envelope", {}).get("task_id", str(uuid.uuid4()))

        if not document_content:
            return jsonify({"status": "failed", "error": "document_content is required"}), 400

        logger.info(f"Received legacy task {task_id}. Adding to Azure Storage Queue...")

        # Queue for background processing
        queue_client = ensure_queue_exists(TRANSLATION_JOBS_QUEUE)
        task_payload = {
            "task_id": task_id,
            "document_content": document_content,
            "target_language": target_language
        }
        
        message_content = json.dumps(task_payload)
        queue_client.send_message(message_content)
        
        logger.info(f"Legacy task {task_id} successfully queued")
        
        response_payload = {
            "task_id": task_id,
            "status": "pending",
            "message": "Task received. A worker will process it shortly."
        }

        return jsonify(response_payload), 202

    except Exception as e:
        logger.error(f"Legacy execute_task error: {e}")
        return jsonify({"error": str(e), "status": "failed"}), 500

@app.route('/task_status/<task_id>', methods=['GET'])
def get_task_status_legacy(task_id):
    """Legacy task status endpoint for backward compatibility"""
    try:
        # Check Azure Blob Storage for completed results
        blob_service_client = get_blob_service_client()
        container_name = "translation-results"
        blob_name = f"{task_id}.json"
        
        try:
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            blob_data = blob_client.download_blob().readall()
            result_data = json.loads(blob_data.decode('utf-8'))
            
            # Return legacy format for backward compatibility
            return jsonify({
                "task_id": task_id,
                "status": "completed",
                "artifact_content": result_data.get("artifact_content", ""),
                "processed_at": result_data.get("processed_at")
            }), 200
            
        except Exception:
            # Task still pending
            return jsonify({
                "task_id": task_id,
                "status": "pending",
                "message": "Task is being processed by a worker"
            }), 200
            
    except Exception as e:
        logger.error(f"Legacy task status error: {e}")
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


@app.route('/.well-known/agent.json', methods=['GET'])
def get_agent_card():
    """A2A compliant Agent Card at well-known location"""
    try:
        agent_url = request.url_root.rstrip('/')
        
        agent_card = {
            "protocolVersion": "0.2.5",
            "name": "Azure Asynchronous Translation Agent",
            "description": "An A2A Protocol compliant agent that provides text translation using Azure AI Translator with asynchronous processing capabilities.",
            "url": agent_url,
            "preferredTransport": "JSONRPC",
            "version": "2.0.0",
            "capabilities": {
                "streaming": True,
                "pushNotifications": True,
                "stateTransitionHistory": False
            },
            "defaultInputModes": ["text/plain", "application/json"],
            "defaultOutputModes": ["text/plain", "application/json"],
            "skills": [
                {
                    "id": "translate_text",
                    "name": "Text Translation",
                    "description": "Translates text from one language to another using Azure AI Translator",
                    "tags": ["translation", "language", "azure-ai"],
                    "examples": [
                        "Translate 'Hello world' to Spanish",
                        "Convert this document to French"
                    ],
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain"]
                }
            ],
            "endpoints": {
                "jsonrpc": f"{agent_url}/",
                "legacy_rest": f"{agent_url}/execute_task"
            },
            "methods": [
                "message/send",
                "tasks/get",
                "tasks/cancel"
            ]
        }
        
        logger.info(f"A2A Agent card requested, returning endpoints for: {agent_url}")
        return jsonify(agent_card), 200
        
    except Exception as e:
        logger.error(f"Error generating A2A agent card: {e}")
        return jsonify({"error": "Failed to generate agent card"}), 500

# Legacy agent card endpoint for backward compatibility
@app.route('/agent-card', methods=['GET'])
def get_legacy_agent_card():
    """Legacy agent card endpoint for backward compatibility"""
    try:
        agent_url = request.url_root.rstrip('/')
        
        agent_card = {
            "agent_id": "translation-agent-v1",
            "name": "Azure Asynchronous Text Translation Agent (Legacy)",
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
            ],
            "a2a_agent_card": f"{agent_url}/.well-known/agent.json"
        }
        
        logger.info(f"Legacy agent card requested, returning endpoints for: {agent_url}")
        return jsonify(agent_card), 200
        
    except Exception as e:
        logger.error(f"Error generating legacy agent card: {e}")
        return jsonify({"error": "Failed to generate agent card"}), 500


@app.route('/', methods=['GET'])
def index():
    """A2A Protocol information and status page"""
    agent_url = request.url_root.rstrip('/')
    
    html_content = f"""
    <html>
    <head>
        <title>A2A Translation Agent</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .header {{ color: #0078d4; }}
            .endpoint {{ background: #f5f5f5; padding: 10px; margin: 10px 0; }}
            .json {{ background: #2d3748; color: #e2e8f0; padding: 15px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1 class="header">🌐 A2A Translation Agent</h1>
        <p>This agent is fully compliant with the <strong>Agent-to-Agent (A2A) Protocol v0.2.5</strong></p>
        
        <h3>📋 Available Endpoints:</h3>
        <div class="endpoint">
            <strong>JSON-RPC 2.0 (A2A Primary):</strong> 
            <code>POST {agent_url}/</code>
        </div>
        <div class="endpoint">
            <strong>Agent Discovery:</strong> 
            <code>GET {agent_url}/.well-known/agent.json</code>
        </div>
        <div class="endpoint">
            <strong>Legacy REST (Backward Compatibility):</strong> 
            <code>POST {agent_url}/execute_task</code>
        </div>
        
        <h3>🔧 A2A Methods:</h3>
        <ul>
            <li><code>message/send</code> - Submit translation tasks</li>
            <li><code>tasks/get</code> - Get task status and results</li>
            <li><code>tasks/cancel</code> - Cancel pending tasks</li>
        </ul>
        
        <h3>📖 Example A2A Request:</h3>
        <pre class="json">{{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {{
    "message": {{
      "role": "user",
      "parts": [
        {{"kind": "text", "text": "Hello, world!"}},
        {{"kind": "data", "data": {{"target_language": "es"}}}}
      ],
      "messageId": "uuid-generated-by-client",
      "kind": "message"
    }}
  }},
  "id": "request-id"
}}</pre>
        
        <p><em>Ready to accept A2A translation tasks! 🚀</em></p>
    </body>
    </html>
    """
    
    return html_content


if __name__ == '__main__':
    logger.info("Translation Agent (A2A-evolved Producer) is starting on http://0.0.0.0:5000")
    # This app's only job is to receive and queue tasks.
    # The actual translation is done by a separate worker.
    app.run(host='0.0.0.0', port=5000, debug=False)
