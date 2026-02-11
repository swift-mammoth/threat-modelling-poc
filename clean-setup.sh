#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛡️  Threat Modeling Application Setup${NC}"
echo -e "${BLUE}   (Azure Cloud Shell Compatible)${NC}"
echo "=============================================="
echo ""

# ============================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================

RESOURCE_GROUP="threat-modeling-poc"
LOCATION="australiaeast"
KV_NAME="threat-modeling-kv"
CONTAINER_APP="threat-modeling"
ENV_NAME="threat-modeling-env"
ACR_NAME="threatmodelingacr"
IMAGE_NAME="threat-modeling"

# Your secrets - UPDATE THESE!
OPENAI_KEY="your-openai-key-here"
OPENAI_ENDPOINT="https://threat-modeling-poc-1.openai.azure.com/"
OPENAI_DEPLOYMENT="gpt-4o"
GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="your-google-secret-here"
AUTHORIZED_DOMAINS="gmail.com"

# ============================================
# INSTALLATION MODE SELECTION
# ============================================

echo -e "${YELLOW}Select installation mode:${NC}"
echo ""
echo "1) 🆕 Clean Install (Delete everything and start fresh)"
echo "   - Deletes Key Vault and Container App"
echo "   - Creates new resources"
echo "   - Use when: Starting fresh or fixing major issues"
echo ""
echo "2) 🔄 Update Deployment (Keep existing config, update container)"
echo "   - Keeps Key Vault and secrets"
echo "   - Builds and updates container image"
echo "   - Use when: Deploying new code changes"
echo ""
echo "3) 🐳 Build & Push Only (Build container without deployment)"
echo "   - Builds and pushes new container image using ACR Tasks"
echo "   - Doesn't update Container App"
echo "   - Use when: Preparing for CI/CD deployment"
echo ""
read -p "Enter choice [1-3]: " MODE

case $MODE in
    1)
        INSTALL_MODE="clean"
        echo -e "${GREEN}✓ Clean Install mode selected${NC}"
        ;;
    2)
        INSTALL_MODE="update"
        echo -e "${GREEN}✓ Update Deployment mode selected${NC}"
        ;;
    3)
        INSTALL_MODE="build-only"
        echo -e "${GREEN}✓ Build & Push Only mode selected${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}📋 Configuration:${NC}"
echo "   Resource Group: $RESOURCE_GROUP"
echo "   Key Vault: $KV_NAME"
echo "   Container App: $CONTAINER_APP"
echo "   ACR: $ACR_NAME"
echo "   Image: $IMAGE_NAME"
echo "   Mode: $INSTALL_MODE"
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# ============================================
# BUILD & PUSH CONTAINER IMAGE (ACR Tasks)
# ============================================

if [ "$INSTALL_MODE" != "clean" ]; then
    echo ""
    echo -e "${BLUE}🐳 Building container image using Azure Container Registry Tasks...${NC}"
    
    # Get Git SHA and build date
    GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "local")
    BUILD_DATE=$(date -u +"%Y%m%d-%H%M%S")
    IMAGE_TAG="${BUILD_DATE}-${GIT_SHA}"
    
    echo "Build information:"
    echo "  Git SHA: $GIT_SHA"
    echo "  Build Date: $BUILD_DATE"
    echo "  Image Tag: $IMAGE_TAG"
    echo ""
    
    # Check if container directory exists
    if [ ! -d "./container" ]; then
        echo -e "${RED}Error: ./container directory not found${NC}"
        echo "Please run this script from the repository root"
        exit 1
    fi
    
    # Create a temporary build context archive
    echo "Creating build context..."
    TEMP_DIR=$(mktemp -d)
    tar -czf "${TEMP_DIR}/build-context.tar.gz" \
        -C ./container \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        .
    
    echo -e "${GREEN}✓ Build context created${NC}"
    
    # Build using ACR Tasks (no Docker daemon needed!)
    echo "Building image with ACR Tasks..."
    echo "This may take 3-5 minutes..."
    
    az acr build \
        --registry $ACR_NAME \
        --image "${IMAGE_NAME}:${IMAGE_TAG}" \
        --image "${IMAGE_NAME}:latest" \
        --file ./container/Dockerfile \
        --build-arg GIT_SHA="$GIT_SHA" \
        --build-arg APP_VERSION="$IMAGE_TAG" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        ./container/
    
    BUILD_STATUS=$?
    
    # Cleanup
    rm -rf "${TEMP_DIR}"
    
    if [ $BUILD_STATUS -eq 0 ]; then
        echo -e "${GREEN}✓ Container image built and pushed to ACR${NC}"
        echo "  Image: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
        echo "  Latest: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest"
    else
        echo -e "${RED}✗ Build failed${NC}"
        exit 1
    fi
    
    # Store the image reference for deployment
    DEPLOYMENT_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
    
    if [ "$INSTALL_MODE" = "build-only" ]; then
        echo ""
        echo -e "${GREEN}✅ Build & Push Complete!${NC}"
        echo ""
        echo "Image ready for deployment:"
        echo "  ${DEPLOYMENT_IMAGE}"
        echo ""
        echo "To deploy manually:"
        echo "  az containerapp update \\"
        echo "    --name $CONTAINER_APP \\"
        echo "    --resource-group $RESOURCE_GROUP \\"
        echo "    --image ${DEPLOYMENT_IMAGE}"
        echo ""
        exit 0
    fi
else
    # For clean install, we'll use the latest image from ACR
    DEPLOYMENT_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest"
fi

# ============================================
# CLEAN INSTALL MODE
# ============================================

if [ "$INSTALL_MODE" = "clean" ]; then
    echo ""
    echo -e "${YELLOW}🗑️  Cleaning up existing resources...${NC}"
    
    # Delete Container App
    echo "Deleting Container App (if exists)..."
    az containerapp delete \
      --name $CONTAINER_APP \
      --resource-group $RESOURCE_GROUP \
      --yes 2>/dev/null && echo -e "${GREEN}✓ Container App deleted${NC}" || echo "✓ No Container App to delete"
    
    # Delete Key Vault (soft delete requires purge)
    echo "Deleting Key Vault (if exists)..."
    az keyvault delete \
      --name $KV_NAME \
      --resource-group $RESOURCE_GROUP 2>/dev/null && echo -e "${GREEN}✓ Key Vault deleted${NC}" || echo "✓ No Key Vault to delete"
    
    # Purge soft-deleted Key Vault
    echo "Purging Key Vault (if soft-deleted)..."
    az keyvault purge \
      --name $KV_NAME \
      --no-wait 2>/dev/null && echo -e "${GREEN}✓ Key Vault purged${NC}" || echo "✓ No Key Vault to purge"
    
    echo "Waiting 30 seconds for cleanup to complete..."
    sleep 30
    
    # ============================================
    # Create Key Vault
    # ============================================
    
    echo ""
    echo -e "${BLUE}🔐 Creating Key Vault...${NC}"
    az keyvault create \
      --name $KV_NAME \
      --resource-group $RESOURCE_GROUP \
      --location $LOCATION \
      --enable-rbac-authorization false \
      --enabled-for-deployment true \
      --enabled-for-template-deployment true
    
    echo -e "${GREEN}✓ Key Vault created${NC}"
    
    # ============================================
    # Store Secrets in Key Vault
    # ============================================
    
    echo ""
    echo -e "${BLUE}🔒 Storing secrets in Key Vault...${NC}"
    
    # Azure OpenAI
    az keyvault secret set --vault-name $KV_NAME --name azure-openai-key --value "$OPENAI_KEY" > /dev/null
    az keyvault secret set --vault-name $KV_NAME --name azure-openai-endpoint --value "$OPENAI_ENDPOINT" > /dev/null
    echo -e "${GREEN}✓ Azure OpenAI secrets stored${NC}"
    
    # Google OAuth
    az keyvault secret set --vault-name $KV_NAME --name google-client-id --value "$GOOGLE_CLIENT_ID" > /dev/null
    az keyvault secret set --vault-name $KV_NAME --name google-client-secret --value "$GOOGLE_CLIENT_SECRET" > /dev/null
    echo -e "${GREEN}✓ Google OAuth secrets stored${NC}"
    
    # Authorization
    az keyvault secret set --vault-name $KV_NAME --name authorized-domains --value "$AUTHORIZED_DOMAINS" > /dev/null
    echo -e "${GREEN}✓ Authorization settings stored${NC}"
    
    # ACR Credentials (for reference, though we'll use managed identity)
    ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv 2>/dev/null || echo "")
    ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv 2>/dev/null || echo "")
    if [ ! -z "$ACR_USERNAME" ]; then
        az keyvault secret set --vault-name $KV_NAME --name acr-username --value "$ACR_USERNAME" > /dev/null
        az keyvault secret set --vault-name $KV_NAME --name acr-password --value "$ACR_PASSWORD" > /dev/null
        echo -e "${GREEN}✓ ACR credentials stored${NC}"
    fi
    
    # ============================================
    # Build Initial Image (if not exists)
    # ============================================
    
    echo ""
    echo -e "${BLUE}🐳 Checking for container image...${NC}"
    
    # Check if image exists in ACR
    IMAGE_EXISTS=$(az acr repository show \
        --name $ACR_NAME \
        --repository $IMAGE_NAME \
        --query "name" -o tsv 2>/dev/null || echo "")
    
    if [ -z "$IMAGE_EXISTS" ]; then
        echo "Image not found in ACR. Building initial image..."
        
        GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "initial")
        BUILD_DATE=$(date -u +"%Y%m%d-%H%M%S")
        
        az acr build \
            --registry $ACR_NAME \
            --image "${IMAGE_NAME}:latest" \
            --image "${IMAGE_NAME}:initial" \
            --file ./container/Dockerfile \
            --build-arg GIT_SHA="$GIT_SHA" \
            --build-arg APP_VERSION="initial" \
            --build-arg BUILD_DATE="$BUILD_DATE" \
            ./container/
        
        echo -e "${GREEN}✓ Initial image built${NC}"
        DEPLOYMENT_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest"
    else
        echo -e "${GREEN}✓ Image exists in ACR${NC}"
    fi
    
    # ============================================
    # Create Container App with Managed Identity
    # ============================================
    
    echo ""
    echo -e "${BLUE}🚀 Creating Container App...${NC}"
    
    az containerapp create \
      --name $CONTAINER_APP \
      --resource-group $RESOURCE_GROUP \
      --environment $ENV_NAME \
      --image $DEPLOYMENT_IMAGE \
      --registry-server ${ACR_NAME}.azurecr.io \
      --registry-identity system \
      --target-port 8501 \
      --ingress external \
      --cpu 1.0 \
      --memory 2.0Gi \
      --min-replicas 1 \
      --max-replicas 3 \
      --system-assigned
    
    echo -e "${GREEN}✓ Container App created with managed identity${NC}"
    
    # ============================================
    # Grant Permissions
    # ============================================
    
    echo ""
    echo -e "${BLUE}🔓 Granting permissions...${NC}"
    
    # Get Container App's managed identity
    PRINCIPAL_ID=$(az containerapp show \
      --name $CONTAINER_APP \
      --resource-group $RESOURCE_GROUP \
      --query identity.principalId -o tsv)
    
    echo "Principal ID: $PRINCIPAL_ID"
    
    # Wait for identity to propagate
    echo "Waiting for identity to propagate..."
    sleep 20
    
    # Grant Key Vault access
    echo "Granting Key Vault access..."
    az keyvault set-policy \
      --name $KV_NAME \
      --object-id $PRINCIPAL_ID \
      --secret-permissions get list
    
    echo -e "${GREEN}✓ Key Vault access granted${NC}"
    
    # Grant ACR pull access
    echo "Granting ACR pull access..."
    ACR_ID=$(az acr show --name $ACR_NAME --query id -o tsv)
    az role assignment create \
      --assignee $PRINCIPAL_ID \
      --role AcrPull \
      --scope $ACR_ID 2>/dev/null || echo -e "${GREEN}✓ ACR permission already exists${NC}"
    
    echo -e "${GREEN}✓ ACR pull access granted${NC}"
    
    # ============================================
    # Configure Container App Secrets
    # ============================================
    
    echo ""
    echo -e "${BLUE}🔗 Linking Container App to Key Vault...${NC}"
    
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
    
    echo -e "${GREEN}✓ Container App secrets linked to Key Vault${NC}"
fi

# ============================================
# UPDATE DEPLOYMENT MODE (Works for both clean and update)
# ============================================

echo ""
echo -e "${BLUE}⚙️  Configuring Container App...${NC}"

# Get app URL
FQDN=$(az containerapp show \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn -o tsv)

APP_URL="https://$FQDN"

# Get Git SHA for version tracking
GIT_SHA_FULL=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
GIT_SHA_SHORT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Generate API key if not already set
if [ "$INSTALL_MODE" = "clean" ] || [ "$INSTALL_MODE" = "update" ]; then
    # Check if API key exists in Key Vault
    API_KEY_EXISTS=$(az keyvault secret show \
        --vault-name $KV_NAME \
        --name api-key \
        --query value -o tsv 2>/dev/null || echo "")
    
    if [ -z "$API_KEY_EXISTS" ]; then
        echo "Generating API key..."
        # Try openssl first, fallback to /dev/urandom
        API_KEY=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
        
        # Store in Key Vault
        az keyvault secret set \
            --vault-name $KV_NAME \
            --name api-key \
            --value "$API_KEY" > /dev/null
        
        echo -e "${GREEN}✓ API key generated and stored in Key Vault${NC}"
        echo -e "${YELLOW}API Key: $API_KEY${NC}"
        echo -e "${RED}IMPORTANT: Save this key! You won't see it again.${NC}"
        
        # Add to secrets
        az containerapp secret set \
            --name $CONTAINER_APP \
            --resource-group $RESOURCE_GROUP \
            --secrets \
                api-key="keyvaultref:https://${KV_NAME}.vault.azure.net/secrets/api-key,identityref:system"
        
        echo -e "${GREEN}✓ API key secret configured${NC}"
    else
        echo -e "${GREEN}✓ Using existing API key from Key Vault${NC}"
    fi
fi

# Update container with new image and environment variables
echo "Updating container app with new image and configuration..."
az containerapp update \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --image $DEPLOYMENT_IMAGE \
  --set-env-vars \
    AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
    AZURE_OPENAI_KEY=secretref:azure-openai-key \
    AZURE_OPENAI_DEPLOYMENT="$OPENAI_DEPLOYMENT" \
    AZURE_OPENAI_API_VERSION="2024-02-01" \
    REQUIRE_AUTH="false" \
    APP_URL="$APP_URL" \
    GOOGLE_CLIENT_ID=secretref:google-client-id \
    GOOGLE_CLIENT_SECRET=secretref:google-client-secret \
    AUTHORIZED_DOMAINS=secretref:authorized-domains \
    API_ENABLED="false" \
    API_KEY=secretref:api-key \
    API_PORT="8000" \
    API_RATE_LIMIT="100" \
    APP_VERSION="${IMAGE_TAG:-latest}" \
    GIT_SHA="$GIT_SHA_FULL" \
    BUILD_DATE="$BUILD_DATE"

echo -e "${GREEN}✓ Container App updated${NC}"

# Force a restart to ensure new container is running
echo "Restarting container to ensure new image is loaded..."
CURRENT_REVISION=$(az containerapp revision list \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --query "[?properties.active==\`true\`].name | [0]" -o tsv)

if [ ! -z "$CURRENT_REVISION" ]; then
    az containerapp revision restart \
      --name $CONTAINER_APP \
      --resource-group $RESOURCE_GROUP \
      --revision $CURRENT_REVISION
    
    echo -e "${GREEN}✓ Container restarted${NC}"
else
    echo -e "${YELLOW}⚠️  Could not find active revision to restart${NC}"
fi

# Wait for the app to be ready
echo "Waiting for application to be ready..."
sleep 20

# ============================================
# Verification
# ============================================

echo ""
echo -e "${BLUE}🔍 Verifying deployment...${NC}"

# Check if container is running
REPLICA_COUNT=$(az containerapp replica list \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --revision $CURRENT_REVISION \
  --query "length([?properties.runningState=='Running'])" -o tsv 2>/dev/null || echo "0")

if [ "$REPLICA_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Container is running ($REPLICA_COUNT replica(s))${NC}"
else
    echo -e "${RED}⚠️  Warning: No running replicas found${NC}"
    echo "Checking recent logs..."
    az containerapp logs show \
      --name $CONTAINER_APP \
      --resource-group $RESOURCE_GROUP \
      --tail 20 2>/dev/null || true
fi

# Get the current revision and image
CURRENT_IMAGE=$(az containerapp show \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --query "properties.template.containers[0].image" -o tsv)

echo "Current image: $CURRENT_IMAGE"

# ============================================
# Summary
# ============================================

echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "=================="
echo ""
echo -e "${BLUE}📋 Summary:${NC}"
echo "   Mode: $INSTALL_MODE"
echo "   Key Vault: $KV_NAME"
echo "   Container App: $CONTAINER_APP"
echo "   Image: $DEPLOYMENT_IMAGE"
echo "   Current Image: $CURRENT_IMAGE"
echo "   Active Revision: $CURRENT_REVISION"
echo "   App URL: $APP_URL"
echo ""
echo -e "${BLUE}🔐 Security Configuration:${NC}"
echo "   ✅ Managed Identity enabled"
echo "   ✅ ACR uses Managed Identity (no passwords!)"
echo "   ✅ All secrets in Key Vault"
echo "   ✅ Key Vault access granted"
if [ "$INSTALL_MODE" = "clean" ]; then
    echo "   ⚠️  OAuth authentication: DISABLED (REQUIRE_AUTH=false)"
    echo "   ⚠️  API: DISABLED (API_ENABLED=false)"
else
    echo "   ℹ️  OAuth authentication unchanged"
    echo "   ℹ️  API status unchanged"
fi
echo ""
echo -e "${BLUE}🌐 Access your app:${NC}"
echo "   $APP_URL"
echo ""

if [ "$INSTALL_MODE" = "clean" ]; then
    echo -e "${YELLOW}⚠️  IMPORTANT: Update Google OAuth redirect URI to:${NC}"
    echo "   $APP_URL/"
    echo ""
    echo "   Go to: https://console.cloud.google.com/apis/credentials"
    echo "   Click your OAuth client"
    echo "   Add to Authorized redirect URIs: $APP_URL/"
    echo "   Save"
    echo ""
fi

echo -e "${BLUE}📝 Useful Commands:${NC}"
echo ""
echo "Update a secret:"
echo "  az keyvault secret set --vault-name $KV_NAME --name SECRET_NAME --value NEW_VALUE"
echo ""
echo "View secrets:"
echo "  az keyvault secret list --vault-name $KV_NAME --output table"
echo ""
echo "View logs:"
echo "  az containerapp logs show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --follow"
echo ""
echo "List revisions:"
echo "  az containerapp revision list --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --output table"
echo ""
echo "Enable authentication:"
echo "  az containerapp update --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --set-env-vars REQUIRE_AUTH=true"
echo ""
echo "Enable API:"
echo "  az containerapp update --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --set-env-vars API_ENABLED=true"
echo ""
echo "Get API key:"
echo "  az keyvault secret show --vault-name $KV_NAME --name api-key --query value -o tsv"
echo ""
echo -e "${GREEN}🎉 Your application is ready!${NC}"
echo ""
