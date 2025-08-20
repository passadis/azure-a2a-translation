#!/bin/bash

# Script to update translation_agent_card.json with dynamic endpoint from environment variables

echo "Updating translation_agent_card.json with dynamic endpoints..."

# Check if TRANSLATION_AGENT_URL is set
if [ -z "$TRANSLATION_AGENT_URL" ]; then
    echo "Warning: TRANSLATION_AGENT_URL environment variable not set. Using default localhost."
    TRANSLATION_AGENT_URL="http://localhost:5203"
fi

echo "Using Translation Agent URL: $TRANSLATION_AGENT_URL"

# Update the translation_agent_card.json file with the correct endpoints
cat > /app/translation_agent_card.json << EOF
{
    "agent_id": "translation-agent-v1",
    "name": "Azure Asynchronous Text Translation Agent",
    "description": "An agent that receives text translation tasks asynchronously using Azure AI Translator, deployed on Azure Container Apps.",
    "skills": [
        {
            "skill_name": "translate_text",
            "endpoint": "${TRANSLATION_AGENT_URL}/execute_task",
            "status_endpoint": "${TRANSLATION_AGENT_URL}/get_task_status",
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
EOF

echo "Successfully updated translation_agent_card.json"

# Start the web application
echo "Starting web GUI application..."
exec "$@"
