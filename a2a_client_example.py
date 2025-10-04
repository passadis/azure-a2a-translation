#!/usr/bin/env python3
"""
A2A Translation Client Example
Demonstrates how to use the Azure A2A Translation Agent
"""

import requests
import json
import uuid
import time
import sys

class A2ATranslationClient:
    def __init__(self, agent_url: str):
        self.agent_url = agent_url.rstrip('/')
        
    def discover_agent(self):
        """Discover agent capabilities"""
        try:
            response = requests.get(f"{self.agent_url}/.well-known/agent.json")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Agent discovery failed: {e}")
            return None
            
    def send_message(self, text: str, target_language: str = "es"):
        """Send A2A translation message"""
        try:
            # Create A2A message
            message = {
                "role": "user",
                "parts": [
                    {"kind": "text", "text": text},
                    {"kind": "data", "data": {"target_language": target_language}}
                ],
                "messageId": str(uuid.uuid4()),
                "kind": "message"
            }
            
            # JSON-RPC 2.0 request
            request = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {"message": message},
                "id": str(uuid.uuid4())
            }
            
            response = requests.post(
                f"{self.agent_url}/",
                json=request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            jsonrpc_response = response.json()
            
            if "error" in jsonrpc_response:
                print(f"❌ JSON-RPC Error: {jsonrpc_response['error']}")
                return None
                
            return jsonrpc_response["result"]
            
        except Exception as e:
            print(f"❌ Send message failed: {e}")
            return None
            
    def get_task(self, task_id: str):
        """Get task status and results"""
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "tasks/get",
                "params": {"id": task_id},
                "id": str(uuid.uuid4())
            }
            
            response = requests.post(
                f"{self.agent_url}/",
                json=request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            jsonrpc_response = response.json()
            
            if "error" in jsonrpc_response:
                print(f"❌ JSON-RPC Error: {jsonrpc_response['error']}")
                return None
                
            return jsonrpc_response["result"]
            
        except Exception as e:
            print(f"❌ Get task failed: {e}")
            return None
            
    def wait_for_completion(self, task_id: str, timeout: int = 60):
        """Wait for task completion"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            task = self.get_task(task_id)
            if not task:
                return None
                
            status = task.get("status", {}).get("state", "unknown")
            
            if status == "completed":
                return task
            elif status in ["failed", "cancelled"]:
                print(f"❌ Task {status}")
                return None
            else:
                print(f"⏳ Task status: {status}")
                time.sleep(3)
                
        print("⏰ Task timeout")
        return None
        
    def translate_text(self, text: str, target_language: str = "es"):
        """Complete translation workflow"""
        print(f"🌐 Translating to {target_language}: {text}")
        print()
        
        # 1. Discover agent
        print("📡 Discovering agent...")
        agent_card = self.discover_agent()
        if agent_card:
            print(f"✅ Found agent: {agent_card.get('name', 'Unknown')}")
            print(f"   Protocol: {agent_card.get('protocolVersion', 'Unknown')}")
        else:
            print("❌ Agent discovery failed, continuing anyway...")
        print()
        
        # 2. Send message
        print("📤 Sending translation request...")
        task = self.send_message(text, target_language)
        if not task:
            return None
            
        task_id = task.get("id")
        print(f"✅ Task created: {task_id}")
        print()
        
        # 3. Wait for completion
        print("⏳ Waiting for translation...")
        completed_task = self.wait_for_completion(task_id)
        if not completed_task:
            return None
            
        # 4. Extract result
        artifacts = completed_task.get("artifacts", [])
        if not artifacts:
            print("❌ No translation result found")
            return None
            
        # Get translation from first artifact
        for artifact in artifacts:
            for part in artifact.get("parts", []):
                if part.get("kind") == "text":
                    translation = part.get("text", "")
                    print(f"✅ Translation completed: {translation}")
                    return translation
                    
        print("❌ No translation text found in artifacts")
        return None

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python a2a_client_example.py <agent_url> [text] [target_language]")
        print("Example: python a2a_client_example.py https://my-agent.example.com")
        sys.exit(1)
        
    agent_url = sys.argv[1]
    text = sys.argv[2] if len(sys.argv) > 2 else "Hello, A2A Protocol!"
    target_language = sys.argv[3] if len(sys.argv) > 3 else "es"
    
    client = A2ATranslationClient(agent_url)
    result = client.translate_text(text, target_language)
    
    if result:
        print()
        print("🎉 Translation successful!")
        print(f"Original: {text}")
        print(f"Translation ({target_language}): {result}")
    else:
        print()
        print("💥 Translation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()