#!/bin/bash
set -e

echo "🧹 Clean Setup - Threat Modeling Application"
echo "=============================================="
echo ""
echo "This script will:"
echo "1. Delete existing Key Vault (if exists)"
echo "2. Delete existing Container App (if exists)"
echo "3. Create fresh Key Vault with all secrets"
echo "4. Create fresh Container App with:"
echo "   • Managed Identity for ACR (no passwords!)"
echo "   • Key Vault integration"
echo "   • All environment variables configured"
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# ============================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================

RESOURCE_GROUP="threat-modeling-poc"
LOCATION="australiaeast"
KV_NAME="threat-modeling-kv"
CONTAINER_APP="threat-modeling"
ENV_NAME="threat-modeling-env"
ACR_NAME="threatmodelingacr"
IMAGE="threatmodelingacr.azurecr.io/threat-modeling:latest"

# Your secrets - UPDATE THESE!
OPENAI_KEY="your-openai-key-here"
OPENAI_ENDPOINT="https://threat-modeling-poc-1.openai.azure.com/"
OPENAI_DEPLOYMENT="gpt-4o"
GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="your-google-secret-here"
AUTHORIZED_DOMAINS="gmail.com"

echo ""
echo "📋 Configuration:"
echo "   Resource Group: $RESOURCE_GROUP"
echo "   Key Vault: $KV_NAME"
echo "   Container App: $CONTAINER_APP"
echo "   Image: $IMAGE"
echo ""
read -p "Looks good? (yes/no): " CONFIRM2

if [ "$CONFIRM2" != "yes" ]; then
    echo "Please edit the script and update the configuration section."
    exit 0
fi

# ============================================
# STEP 1: Clean Up Existing Resources
# ============================================

echo ""
echo "🗑️  Step 1: Cleaning up existing resources..."

# Delete Container App
echo "Deleting Container App (if exists)..."
az containerapp delete \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --yes 2>/dev/null && echo "✓ Container App deleted" || echo "✓ No Container App to delete"

# Delete Key Vault (soft delete requires purge)
echo "Deleting Key Vault (if exists)..."
az keyvault delete \
  --name $KV_NAME \
  --resource-group $RESOURCE_GROUP 2>/dev/null && echo "✓ Key Vault deleted" || echo "✓ No Key Vault to delete"

# Purge soft-deleted Key Vault
echo "Purging Key Vault (if soft-deleted)..."
az keyvault purge \
  --name $KV_NAME \
  --no-wait 2>/dev/null && echo "✓ Key Vault purged" || echo "✓ No Key Vault to purge"

echo "Waiting 30 seconds for cleanup to complete..."
sleep 30

# ============================================
# STEP 2: Create Key Vault
# ============================================

echo ""
echo "🔐 Step 2: Creating Key Vault..."
az keyvault create \
  --name $KV_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --enable-rbac-authorization false \
  --enabled-for-deployment true \
  --enabled-for-template-deployment true

echo "✓ Key Vault created"

# ============================================
# STEP 3: Store Secrets in Key Vault
# ============================================

echo ""
echo "🔑 Step 3: Storing secrets in Key Vault..."

# Azure OpenAI
az keyvault secret set --vault-name $KV_NAME --name azure-openai-key --value "$OPENAI_KEY" > /dev/null
az keyvault secret set --vault-name $KV_NAME --name azure-openai-endpoint --value "$OPENAI_ENDPOINT" > /dev/null
echo "✓ Azure OpenAI secrets stored"

# Google OAuth
az keyvault secret set --vault-name $KV_NAME --name google-client-id --value "$GOOGLE_CLIENT_ID" > /dev/null
az keyvault secret set --vault-name $KV_NAME --name google-client-secret --value "$GOOGLE_CLIENT_SECRET" > /dev/null
echo "✓ Google OAuth secrets stored"

# Authorization
az keyvault secret set --vault-name $KV_NAME --name authorized-domains --value "$AUTHORIZED_DOMAINS" > /dev/null
echo "✓ Authorization settings stored"

# ACR Credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
az keyvault secret set --vault-name $KV_NAME --name acr-username --value "$ACR_USERNAME" > /dev/null
az keyvault secret set --vault-name $KV_NAME --name acr-password --value "$ACR_PASSWORD" > /dev/null
echo "✓ ACR credentials stored"

echo ""
echo "📋 Secrets in Key Vault:"
az keyvault secret list --vault-name $KV_NAME --query "[].name" -o tsv | sort

# ============================================
# STEP 4: Create Container App with Managed Identity
# ============================================

echo ""
echo "🚀 Step 4: Creating Container App..."

# Create with managed identity and Key Vault references
az containerapp create \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image $IMAGE \
  --registry-server ${ACR_NAME}.azurecr.io \
  --registry-identity system \
  --target-port 8000 \
  --ingress external \
  --cpu 1.0 \
  --memory 2.0Gi \
  --min-replicas 1 \
  --max-replicas 1 \
  --system-assigned

echo "✓ Container App created with managed identity"

# ============================================
# STEP 5: Grant Permissions
# ============================================

echo ""
echo "🔓 Step 5: Granting permissions..."

# Get Container App's managed identity
PRINCIPAL_ID=$(az containerapp show \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --query identity.principalId -o tsv)

echo "Principal ID: $PRINCIPAL_ID"

# Wait for identity to propagate
echo "Waiting for identity to propagate..."
sleep 15

# Grant Key Vault access
echo "Granting Key Vault access..."
az keyvault set-policy \
  --name $KV_NAME \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list

echo "✓ Key Vault access granted"

# Grant ACR pull access
echo "Granting ACR pull access..."
ACR_ID=$(az acr show --name $ACR_NAME --query id -o tsv)
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role AcrPull \
  --scope $ACR_ID 2>/dev/null || echo "✓ ACR permission already exists"

echo "✓ ACR pull access granted"

# ============================================
# STEP 6: Configure Container App Secrets
# ============================================

echo ""
echo "🔗 Step 6: Linking Container App to Key Vault..."

KV_URL="https://${KV_NAME}.vault.azure.net"

# Set secrets to reference Key Vault
az containerapp secret set \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --secrets \
    azure-openai-endpoint="keyvaultref:${KV_URL}/secrets/azure-openai-endpoint,identityref:system" \
    azure-openai-key="keyvaultref:${KV_URL}/secrets/azure-openai-key,identityref:system" \
    google-client-id="keyvaultref:${KV_URL}/secrets/google-client-id,identityref:system" \
    google-client-secret="keyvaultref:${KV_URL}/secrets/google-client-secret,identityref:system" \
    authorized-domains="keyvaultref:${KV_URL}/secrets/authorized-domains,identityref:system"

echo "✓ Container App secrets linked to Key Vault"

# ============================================
# STEP 7: Configure Environment Variables
# ============================================

echo ""
echo "⚙️  Step 7: Configuring environment variables..."

# Get app URL
FQDN=$(az containerapp show \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn -o tsv)

APP_URL="https://$FQDN"

# Update environment variables
az containerapp update \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars \
    AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
    AZURE_OPENAI_KEY=secretref:azure-openai-key \
    AZURE_OPENAI_DEPLOYMENT="$OPENAI_DEPLOYMENT" \
    AZURE_OPENAI_API_VERSION="2025-01-01-preview" \
    REQUIRE_AUTH="true" \
    APP_URL="$APP_URL" \
    GOOGLE_CLIENT_ID=secretref:google-client-id \
    GOOGLE_CLIENT_SECRET=secretref:google-client-secret \
    AUTHORIZED_DOMAINS=secretref:authorized-domains

echo "✓ Environment variables configured"

# ============================================
# STEP 8: Summary
# ============================================

echo ""
echo "✅ Setup Complete!"
echo "=================="
echo ""
echo "📋 Summary:"
echo "   Key Vault: $KV_NAME"
echo "   Container App: $CONTAINER_APP"
echo "   App URL: $APP_URL"
echo ""
echo "🔐 Security Configuration:"
echo "   ✅ Managed Identity enabled"
echo "   ✅ ACR uses Managed Identity (no passwords!)"
echo "   ✅ All secrets in Key Vault"
echo "   ✅ Key Vault access granted"
echo "   ✅ OAuth enabled"
echo ""
echo "🌐 Access your app:"
echo "   $APP_URL"
echo ""
echo "⚠️  IMPORTANT: Update Google OAuth redirect URI to:"
echo "   $APP_URL/"
echo ""
echo "   Go to: https://console.cloud.google.com/apis/credentials"
echo "   Click your OAuth client"
echo "   Add to Authorized redirect URIs: $APP_URL/"
echo "   Save"
echo ""
echo "🔄 To update a secret:"
echo "   az keyvault secret set --vault-name $KV_NAME --name SECRET_NAME --value NEW_VALUE"
echo ""
echo "📝 To view secrets:"
echo "   az keyvault secret list --vault-name $KV_NAME --output table"
echo ""
echo "📊 To view logs:"
echo "   az containerapp logs show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --follow"
echo ""
echo "🎉 Your application is ready!"
echo ""
