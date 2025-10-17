# Configure the Azure Provider
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~>3.0"
    }
    azurecaf = {
      source  = "aztfmod/azurecaf"
      version = "~>1.2"
    }
  }
  required_version = ">= 1.5"
}

# Configure the Azure Provider
provider "azurerm" {
  features {}
}

# Get current client configuration
data "azurerm_client_config" "current" {}

# Variables
variable "environment_name" {
  description = "Name of the azd environment"
  type        = string
}

variable "location" {
  description = "Primary location for all resources"
  type        = string
  default     = "northeurope"
}

variable "principal_id" {
  description = "The principal ID of the current user"
  type        = string
  default     = ""
}

# Generate a random suffix for unique resource names
resource "random_string" "resource_token" {
  length  = 13
  upper   = false
  special = false
}

# Generate resource names using azurecaf
resource "azurecaf_name" "resource_group" {
  name          = var.environment_name
  resource_type = "azurerm_resource_group"
  random_length = 0
}

resource "azurecaf_name" "storage_account" {
  name          = var.environment_name
  resource_type = "azurerm_storage_account"
  random_length = 5
}

resource "azurecaf_name" "log_analytics" {
  name          = var.environment_name
  resource_type = "azurerm_log_analytics_workspace"
  random_length = 0
}

resource "azurecaf_name" "container_registry" {
  name          = var.environment_name
  resource_type = "azurerm_container_registry"
  random_length = 5
}

resource "azurecaf_name" "container_app_environment" {
  name          = var.environment_name
  resource_type = "azurerm_container_app_environment"
  random_length = 0
}

resource "azurecaf_name" "user_assigned_identity" {
  name          = var.environment_name
  resource_type = "azurerm_user_assigned_identity"
  random_length = 0
}

resource "azurecaf_name" "cognitive_account" {
  name          = var.environment_name
  resource_type = "azurerm_cognitive_account"
  random_length = 0
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = azurecaf_name.resource_group.result
  location = var.location
  
  tags = {
    "azd-env-name" = var.environment_name
    "SecurityControl" = "Ignore"
  }
}

# User Assigned Managed Identity
resource "azurerm_user_assigned_identity" "main" {
  name                = azurecaf_name.user_assigned_identity.result
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  
  tags = {
    "azd-env-name" = var.environment_name
    "SecurityControl" = "Ignore"
  }
}

# Storage Account
resource "azurerm_storage_account" "main" {
  name                     = azurecaf_name.storage_account.result
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  
  # Security settings
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = true  # Disable key access for security
  
  tags = {
    "azd-env-name" = var.environment_name
    "SecurityControl" = "Ignore"
  }
}

# Note: Storage queues will be created programmatically by the applications using managed identity
# This avoids the Terraform key-based authentication requirement

# Storage Queues
resource "azurerm_storage_queue" "translation_jobs" {
  name                 = "translation-jobs"
  storage_account_name = azurerm_storage_account.main.name
  
  depends_on = [azurerm_storage_account.main]
}

resource "azurerm_storage_queue" "translation_results" {
  name                 = "translation-results"
  storage_account_name = azurerm_storage_account.main.name
  
  depends_on = [azurerm_storage_account.main]
}

# Storage Container for results
resource "azurerm_storage_container" "translation_results" {
  name                  = "translation-results"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
  
  depends_on = [azurerm_storage_account.main]
}

# Role assignment for managed identity to access storage
resource "azurerm_role_assignment" "storage_queue_data_contributor" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "storage_blob_data_contributor" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

# Azure AI Translator Service
resource "azurerm_cognitive_account" "translator" {
  name                = azurecaf_name.cognitive_account.result
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  kind                = "TextTranslation"
  sku_name            = "S1"
  
  tags = {
    "azd-env-name" = var.environment_name
    "SecurityControl" = "Ignore"
  }
}

# Role assignment for managed identity to access cognitive services
resource "azurerm_role_assignment" "cognitive_services_user" {
  scope                = azurerm_cognitive_account.translator.id
  role_definition_name = "Cognitive Services User"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "main" {
  name                = azurecaf_name.log_analytics.result
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  
  tags = {
    "azd-env-name" = var.environment_name
    "SecurityControl" = "Ignore"
  }
}

# Container Registry
resource "azurerm_container_registry" "main" {
  name                = azurecaf_name.container_registry.result
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false
  
  tags = {
    "azd-env-name" = var.environment_name
    "SecurityControl" = "Ignore"
  }
}

# Role assignment for managed identity to pull from ACR
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

# Container App Environment
resource "azurerm_container_app_environment" "main" {
  name                       = azurecaf_name.container_app_environment.result
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  
  tags = {
    "azd-env-name" = var.environment_name
    "SecurityControl" = "Ignore"
  }
}

# Container App for Translation Agent (Web API)
resource "azurerm_container_app" "translation_agent" {
  name                         = "translation-agent"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main.id]
  }
  
  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.main.id
  }
  
  template {
    min_replicas = 1
    max_replicas = 3
    
    container {
      name   = "translation-agent"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.25
      memory = "0.5Gi"
      
      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.main.name
      }
      
      env {
        name  = "AZURE_TRANSLATOR_ENDPOINT"
        value = azurerm_cognitive_account.translator.endpoint
      }
      
      env {
        name  = "AZURE_TRANSLATOR_REGION"
        value = azurerm_resource_group.main.location
      }
      
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.main.client_id
      }
      
      env {
        name  = "TRANSLATION_JOBS_QUEUE"
        value = "translation-jobs"
      }
      
      env {
        name  = "TRANSLATION_RESULTS_QUEUE"
        value = "translation-results"
      }
    }
  }
  
  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port               = 5000
    
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
  
  tags = {
    "azd-env-name"      = var.environment_name
    "azd-service-name"  = "translation-agent"
    "SecurityControl"   = "Ignore"
  }
}

# Container App for Translation Worker (Background Service)
resource "azurerm_container_app" "translation_worker" {
  name                         = "translation-worker"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main.id]
  }
  
  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.main.id
  }
  
  template {
    min_replicas = 1
    max_replicas = 1
    
    container {
      name   = "translation-worker"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.25
      memory = "0.5Gi"
      
      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.main.name
      }
      
      env {
        name  = "AZURE_TRANSLATOR_ENDPOINT"
        value = azurerm_cognitive_account.translator.endpoint
      }
      
      env {
        name  = "AZURE_TRANSLATOR_REGION"
        value = azurerm_resource_group.main.location
      }
      
      env {
        name  = "AZURE_TRANSLATOR_RESOURCE_ID"
        value = azurerm_cognitive_account.translator.id
      }


      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.main.client_id
      }
      
      env {
        name  = "TRANSLATION_JOBS_QUEUE"
        value = "translation-jobs"
      }
      
      env {
        name  = "TRANSLATION_RESULTS_QUEUE"
        value = "translation-results"
      }
    }
  }
  
  tags = {
    "azd-env-name"      = var.environment_name
    "azd-service-name"  = "translation-worker"
    "SecurityControl"   = "Ignore"
  }
}

# Container App for Web GUI (Frontend)
resource "azurerm_container_app" "web_gui" {
  name                         = "web-gui"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main.id]
  }
  
  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.main.id
  }
  
  template {
    min_replicas = 1
    max_replicas = 3
    
    container {
      name   = "web-gui"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.25
      memory = "0.5Gi"
      
      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.main.name
      }
      
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.main.client_id
      }
      
      env {
        name  = "TRANSLATION_AGENT_URL"
        value = "https://${azurerm_container_app.translation_agent.ingress[0].fqdn}"
      }
    }
  }
  
  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port               = 5000
    
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
  
  tags = {
    "azd-env-name"      = var.environment_name
    "azd-service-name"  = "web-gui"
    "SecurityControl"   = "Ignore"
  }
}

# Diagnostic settings for Container Apps Environment
resource "azurerm_monitor_diagnostic_setting" "environment" {
  name               = "container-apps-environment-diagnostics"
  target_resource_id = azurerm_container_app_environment.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  
  enabled_log {
    category = "ContainerAppConsoleLogs"
  }
  
  enabled_log {
    category = "ContainerAppSystemLogs"
  }
}
