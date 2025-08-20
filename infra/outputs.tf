# Output values for azd
output "AZURE_LOCATION" {
  description = "The primary Azure region"
  value       = var.location
}

output "AZURE_TENANT_ID" {
  description = "The Azure tenant ID"
  value       = data.azurerm_client_config.current.tenant_id
}

output "AZURE_SUBSCRIPTION_ID" {
  description = "The Azure subscription ID"
  value       = data.azurerm_client_config.current.subscription_id
}

output "AZURE_RESOURCE_GROUP" {
  description = "The resource group name"
  value       = azurerm_resource_group.main.name
}

output "RESOURCE_GROUP_ID" {
  description = "Resource group ID"
  value       = azurerm_resource_group.main.id
}

output "AZURE_STORAGE_ACCOUNT_NAME" {
  description = "The storage account name"
  value       = azurerm_storage_account.main.name
}

output "AZURE_CONTAINER_REGISTRY_ENDPOINT" {
  description = "The container registry login server"
  value       = azurerm_container_registry.main.login_server
}

output "AZURE_CONTAINER_REGISTRY_NAME" {
  description = "The container registry name"
  value       = azurerm_container_registry.main.name
}

output "AZURE_CONTAINER_APPS_ENVIRONMENT_ID" {
  description = "The container app environment ID"
  value       = azurerm_container_app_environment.main.id
}

output "AZURE_CONTAINER_APPS_ENVIRONMENT_NAME" {
  description = "The container app environment name"
  value       = azurerm_container_app_environment.main.name
}

output "AZURE_TRANSLATOR_ENDPOINT" {
  description = "The Azure Translator service endpoint"
  value       = azurerm_cognitive_account.translator.endpoint
}

output "AZURE_TRANSLATOR_REGION" {
  description = "The Azure Translator service region"
  value       = azurerm_resource_group.main.location
}

output "AZURE_USER_ASSIGNED_IDENTITY_CLIENT_ID" {
  description = "The user assigned managed identity client ID"
  value       = azurerm_user_assigned_identity.main.client_id
}

output "TRANSLATION_AGENT_URL" {
  description = "The URL of the translation agent container app"
  value       = "https://${azurerm_container_app.translation_agent.ingress[0].fqdn}"
}

output "WEB_GUI_URL" {
  description = "The URL of the web GUI container app"
  value       = "https://${azurerm_container_app.web_gui.ingress[0].fqdn}"
}

output "TRANSLATION_JOBS_QUEUE_NAME" {
  description = "The name of the translation jobs queue"
  value       = "translation-jobs"
}

output "TRANSLATION_RESULTS_QUEUE_NAME" {
  description = "The name of the translation results queue"
  value       = "translation-results"
}
