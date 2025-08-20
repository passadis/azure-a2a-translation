# Translation A2A Service - Azure Deployment

This project implements an Agent-to-Agent (A2A) translation service using Azure Container Apps, Storage Queues, and AI Translator services.

## 🚀 Quick Deploy with Azure Developer CLI

Deploy this entire solution to Azure with just two commands:

```bash
azd auth login
azd up
```

That's it! The `azd up` command will:
- Initialize the project environment
- Provision all Azure infrastructure using Terraform
- Build and deploy the containerized applications
- Configure managed identity and RBAC permissions
- Set up monitoring and logging

**Total deployment time: ~5-10 minutes**

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

## Prerequisites

1. Azure subscription
2. Azure CLI installed
3. Azure Developer CLI (azd) installed
4. Terraform installed
5. Docker installed (for building images)

## Deployment Steps

### Option 1: One-Command Deployment (Recommended)

```bash
azd auth login
azd up
```

The `azd up` command handles everything automatically - infrastructure provisioning and application deployment in one go!

### Option 2: Step-by-Step Deployment

If you prefer to see each step:

### 1. Initialize Azure Developer CLI

```bash
cd new_a2a
azd auth login
azd init
```

### 2. Set Environment Variables (Optional)

```bash
azd env set AZURE_LOCATION northeurope  # Default: westeurope
```

### 3. Deploy Infrastructure

```bash
azd provision
```

This will:
- Create a resource group in North Europe
- Deploy Azure Container Registry
- Deploy Azure Storage Account with queues
- Deploy Azure AI Translator service
- Deploy Container App Environment
- Set up Managed Identity and RBAC permissions
- Create Log Analytics workspace for monitoring

### 4. Build and Deploy Applications

```bash
azd deploy
```

This will:
- Build Docker images for both services
- Push images to Azure Container Registry
- Deploy Container Apps with the built images

### 5. Verify Deployment

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

## Configuration

The services are configured through environment variables:

- `AZURE_STORAGE_ACCOUNT_NAME`: Storage account name (set by Terraform)
- `AZURE_TRANSLATOR_ENDPOINT`: Translator service endpoint (set by Terraform)
- `AZURE_TRANSLATOR_REGION`: Azure region (set by Terraform)
- `AZURE_CLIENT_ID`: Managed identity client ID (set by Terraform)
- `TRANSLATION_JOBS_QUEUE`: Jobs queue name (default: "translation-jobs")
- `TRANSLATION_RESULTS_QUEUE`: Results queue name (default: "translation-results")

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

### Check Container Logs
```bash
azd logs
```

### Verify Queue Messages
Use Azure Storage Explorer or Azure Portal to check queue status

### Test Managed Identity
Check that the Container Apps have the correct identity assignments in the Azure Portal

## Cleanup

To remove all resources:
```bash
azd down
```
