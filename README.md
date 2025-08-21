<p align="center">
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=azure,terraform,vscode,python,html,css,github" />
  </a>
</p>

<h1 align="center">Translation A2A Service - Azure Deployment</h1>

![a2a-main](https://github.com/user-attachments/assets/95145d93-3365-455e-9f86-7af365e785b7)


This project implements an Agent-to-Agent (A2A) translation service using Azure Container Apps, Storage Queues, and AI Translator services.

## Deployment Steps

### Initialize the Project

```bash
azd init --template passadis/azure-a2a-translation
```
### You will get asked to select an Environment name and the build takes over

## ✨ What Makes This Template Special

- **🎯 Complete End-to-End Solution**: Web GUI + API + Background Worker + AI Translation
- **🔒 Security First**: Zero API keys - 100% Managed Identity authentication
- **📦 Container Apps Native**: Built specifically for Azure Container Apps with proper scaling
- **🏗️ Infrastructure as Code**: Terraform with Azure Verified Modules for best practices
- **🔄 Async Architecture**: Queue-based processing for reliable, scalable translations
- **📊 Production Ready**: Includes monitoring, logging, and health checks
- **💰 Cost Optimized**: Scale-to-zero capabilities and efficient resource sizing
- **🚀 azd Compatible**: Perfect template for Azure Developer CLI community

## Architecture

- **Translation Agent**: A Flask web API that receives translation requests and queues them
- **Translation Worker**: A background service that processes translation jobs from the queue
- **Azure Storage Queue**: Message queue system for asynchronous job processing
- **Azure AI Translator**: Cognitive service for text translation
- **Azure Container Apps**: Hosting platform for both services
- **Managed Identity**: Secure authentication without keys

## Other methods:

## Prerequisites

1. Azure subscription
2. Azure CLI installed
3. Azure Developer CLI (azd) installed
4. Docker Desktop installed and running
5. Git installed

## 🚀 Quick Deploy with Azure Developer CLI

Deploy this entire solution to Azure with just two commands:

```bash
azd auth login
azd up
```
## Remember you should have logged in with Azure CLI or switched to your target subscription:
```bash
az login
az account set --subscription <your-subscription-id>
```

That's it! The `azd up` command will:
- Initialize the project environment
- Provision all Azure infrastructure using Terraform
- Build and deploy the containerized applications
- Configure managed identity and RBAC permissions
- Set up monitoring and logging

**Total deployment time: ~5-10 minutes**

### Start Docker

Make sure Docker Desktop is running before deployment:

```bash
# On Windows, start Docker Desktop application
# On Linux/macOS, ensure Docker daemon is running
docker --version
```

### Deploy the Application

```bash
azd auth login
azd up
```

The `azd up` command handles everything automatically - infrastructure provisioning and application deployment in one go!

### Verify Deployment

Check the deployment status:
```bash
azd show
```

Get the application URLs:
```bash
azd env get-values
```

Access your deployed application:
- **Web GUI**: Open `WEB_GUI_URL` in your browser for the translation interface
- **Translation API**: Use `TRANSLATION_AGENT_URL` for direct API access
- **Agent Discovery**: Get agent capabilities at `TRANSLATION_AGENT_URL/agent-card`

## Alternative Deployment Methods

### Option 1: Step-by-Step Deployment

If you prefer to see each step after initializing with `azd init --template`:

```bash
# 1. Set Environment Variables (Optional)
azd env set AZURE_LOCATION northeurope  # Default: westeurope

# 2. Deploy Infrastructure
azd provision

# 3. Build and Deploy Applications
azd deploy

# 4. Verify Deployment
azd show
```

### Option 2: Clone Repository (Traditional Method)

If you prefer to clone the repository directly:

```bash
# Clone the repository
git clone https://github.com/passadis/azure-a2a-translation.git
cd azure-a2a-translation

# Ensure Docker is running
docker --version

# Deploy everything
azd auth login
azd up
```

## Usage

### Using the Web Interface

1. Open the Web GUI URL in your browser
2. Upload a text file (.txt)
3. Select target language
4. Click "Translate"
5. View results in real-time as they complete

### Using the API Directly

### Using the API Directly

Submit a Translation Request:

```bash
curl -X POST "https://your-translation-agent-url/execute_task" \
  -H "Content-Type: application/json" \
  -d '{
    "envelope": {
      "task_id": "test-123",
      "target_language": "es"
    },
    "parts": {
      "document_content": "Hello, world!"
    }
  }'
```

Check Task Status:
```bash
curl "https://your-translation-agent-url/task_status/test-123"
```

### Check Service Health

```bash
curl "https://your-translation-agent-url/health"
curl "https://your-web-gui-url/health"
```

### Agent Discovery

```bash
# Get agent capabilities and endpoints (dynamically generated by the agent)
curl "https://your-translation-agent-url/agent-card"
```

**Note**: Agent discovery is now fully dynamic. The translation agent publishes its own capabilities and current endpoints through the `/agent-card` endpoint, eliminating the need for static configuration files.

## Configuration

The services are configured through environment variables:

- `AZURE_STORAGE_ACCOUNT_NAME`: Storage account name (set by Terraform)
- `AZURE_TRANSLATOR_ENDPOINT`: Translator service endpoint (set by Terraform)
- `AZURE_TRANSLATOR_REGION`: Azure region (set by Terraform)
- `AZURE_TRANSLATOR_RESOURCE_ID`: Translator resource ID for Entra ID authentication (set by Terraform)
- `AZURE_CLIENT_ID`: Managed identity client ID (set by Terraform)
- `TRANSLATION_JOBS_QUEUE`: Jobs queue name (default: "translation-jobs")
- `TRANSLATION_RESULTS_QUEUE`: Results queue name (default: "translation-results")

## User Experience

### True Non-Blocking A2A Experience

This template delivers a genuinely asynchronous Agent-to-Agent experience:

1. **Immediate Response**: Submit translation requests and get instant confirmation
2. **Stay Productive**: Continue submitting more translations while others process
3. **Real-Time Updates**: See results appear automatically as they complete
4. **No Waiting**: Never blocked waiting for translations to finish
5. **History Management**: View up to 5 recent translations with clean history option

## Security Features

- **No API Keys**: Uses Azure Managed Identity for all authentication
- **RBAC**: Least privilege access to Azure services
- **Secure Storage**: Storage account configured without public access
- **TLS**: All communication encrypted in transit
- **Container Security**: Uses slim Python base images

## Monitoring

- Application logs available in Azure Log Analytics
- Container App metrics in Azure Monitor
- Storage queue metrics available
- Translator service usage metrics available

## Scaling

- Translation Agent: Scales 1-3 instances based on HTTP load
- Translation Worker: Runs single instance (can be increased if needed)
- Queue-based architecture allows for independent scaling

## Cost Optimization

- Uses Basic SKU for Container Registry
- Standard LRS for Storage Account
- S1 tier for Translator service (pay-per-use)
- Container Apps scale to zero when not in use

## Troubleshooting

### Common Issues

### Common Issues

#### Authentication Error (401 Unauthorized)
- **Issue**: Translation worker gets "401 Client Error: Unauthorized" when calling Azure Translator
- **Cause**: Missing Entra ID authentication headers for global endpoint
- **Solution**: The template includes proper authentication headers (`Ocp-Apim-ResourceId` and `Ocp-Apim-Subscription-Region`). If you modify the code, ensure these headers are included when using the global translator endpoint.

#### Queue Messages Not Processing
- **Issue**: Translation worker shows "No messages found" even though agent is queuing messages
- **Cause**: Worker crashed or stuck messages due to visibility timeout
- **Solution**: Restart the translation worker:
  ```bash
  az containerapp revision restart --name translation-worker --resource-group <your-resource-group>
  ```

#### Worker Stops Processing After First Job
- **Issue**: First translation succeeds, but subsequent jobs stay "pending"
- **Cause**: Message visibility timeout or worker exception
- **Solution**: Check worker logs and restart if needed:
  ```bash
  az containerapp logs show --name translation-worker --resource-group <your-resource-group> --follow
  ```

#### Docker Build Fails
- **Issue**: Docker build fails with "no such file or directory"
- **Solution**: Ensure Docker Desktop is running and you're in the correct directory:
  ```bash
  docker --version
  cd azure-a2a-translation
  ```

#### Missing .env File Error
- **Issue**: Build fails because .env file is missing
- **Solution**: The Dockerfiles now handle missing .env files automatically. If you still see issues, create an empty .env file:
  ```bash
  touch .env
  ```

#### Static Directory Missing (Web GUI)
- **Issue**: Web GUI build fails due to missing static directory
- **Solution**: The static directory and basic files are now included in the repository. If missing, they will be created automatically during build.


### Verify Queue Messages
Use Azure Storage Explorer or Azure Portal to check queue status

### Test Managed Identity
Check that the Container Apps have the correct identity assignments in the Azure Portal

### Docker Build Locally (for testing)
```bash
# Test translation agent build
docker build -f translation-agent.Dockerfile -t test-agent .

# Test translation worker build  
docker build -f translation-worker.Dockerfile -t test-worker .

# Test web GUI build
cd web-gui
docker build -f web-gui.Dockerfile -t test-web-gui .
```

## Cleanup

To remove all resources:
```bash
azd down
```
