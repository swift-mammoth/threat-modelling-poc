#!/bin/bash
set -e

echo "🔑 Updating Secrets in Existing Key Vault"
echo ""

# Configuration
RESOURCE_GROUP="threat-modeling-poc"
KV_NAME="threat-modeling-kv"
CONTAINER_APP="threat-modeling"

# Your secrets - UPDATE THESE
OPENAI_KEY="your-openai-key-here"
OPENAI_ENDPOINT="https://threat-modeling-poc-1.openai.azure.com/"
GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="your-google-secret-here"
AUTHORIZED_DOMAINS="gmail.com"

echo "📋 Checking Key Vault exists..."
az keyvault show --name $KV_NAME --resource-group $RESOURCE_GROUP > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Key Vault $KV_NAME not found!"
    echo "Run ./setup-keyvault.sh first to create it."
    exit 1
fi

echo "✓ Key Vault found: $KV_NAME"
echo ""

echo "🔑 Updating secrets in Key Vault..."

# Update OpenAI secrets
echo "Updating Azure OpenAI secrets..."
az keyvault secret set --vault-name $KV_NAME --name azure-openai-key --value "$OPENAI_KEY" > /dev/null
az keyvault secret set --vault-name $KV_NAME --name azure-openai-endpoint --value "$OPENAI_ENDPOINT" > /dev/null

# Update Google OAuth secrets
echo "Updating Google OAuth secrets..."
az keyvault secret set --vault-name $KV_NAME --name google-client-id --value "$GOOGLE_CLIENT_ID" > /dev/null
az keyvault secret set --vault-name $KV_NAME --name google-client-secret --value "$GOOGLE_CLIENT_SECRET" > /dev/null

# Update authorization settings
echo "Updating authorization settings..."
az keyvault secret set --vault-name $KV_NAME --name authorized-domains --value "$AUTHORIZED_DOMAINS" > /dev/null

# Update ACR credentials
echo "Updating ACR credentials..."
ACR_USERNAME=$(az acr credential show --name threatmodelingacr --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name threatmodelingacr --query "passwords[0].value" -o tsv)
az keyvault secret set --vault-name $KV_NAME --name acr-username --value "$ACR_USERNAME" > /dev/null
az keyvault secret set --vault-name $KV_NAME --name acr-password --value "$ACR_PASSWORD" > /dev/null

echo ""
echo "✅ All secrets updated in Key Vault!"
echo ""

# List current secrets
echo "📋 Current secrets in Key Vault:"
az keyvault secret list --vault-name $KV_NAME --query "[].name" -o tsv | sort

echo ""
echo "🔗 Linking Container App to Key Vault secrets..."

# Get app URL
FQDN=$(az containerapp show \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn -o tsv)

APP_URL="https://$FQDN"

# Update Container App secrets to reference Key Vault
KV_URL="https://${KV_NAME}.vault.azure.net"

echo "Setting Container App secrets to reference Key Vault..."
az containerapp secret set \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --secrets \
    azure-openai-endpoint="keyvaultref:${KV_URL}/secrets/azure-openai-endpoint,identityref:system" \
    azure-openai-key="keyvaultref:${KV_URL}/secrets/azure-openai-key,identityref:system" \
    google-client-id="keyvaultref:${KV_URL}/secrets/google-client-id,identityref:system" \
    google-client-secret="keyvaultref:${KV_URL}/secrets/google-client-secret,identityref:system" \
    authorized-domains="keyvaultref:${KV_URL}/secrets/authorized-domains,identityref:system"

echo "Updating environment variables to use secrets..."
az containerapp update \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars \
    AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
    AZURE_OPENAI_KEY=secretref:azure-openai-key \
    AZURE_OPENAI_DEPLOYMENT="gpt-4o" \
    AZURE_OPENAI_API_VERSION="2025-01-01-preview" \
    REQUIRE_AUTH="true" \
    APP_URL="$APP_URL" \
    GOOGLE_CLIENT_ID=secretref:google-client-id \
    GOOGLE_CLIENT_SECRET=secretref:google-client-secret \
    AUTHORIZED_DOMAINS=secretref:authorized-domains

echo ""
echo "✅ Container App configured!"
echo ""
echo "📋 Summary:"
echo "   Key Vault: $KV_NAME"
echo "   Secrets: Updated"
echo "   Container App: Linked to Key Vault"
echo "   App URL: $APP_URL"
echo ""
echo "🔄 To update a secret in the future:"
echo "   az keyvault secret set --vault-name $KV_NAME --name SECRET_NAME --value NEW_VALUE"
echo ""
echo "📝 Container App will pick up changes within ~30 seconds"
echo ""
