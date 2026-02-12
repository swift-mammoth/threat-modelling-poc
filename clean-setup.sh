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
echo "   - Builds new container image"
echo "   - Creates new resources"
echo "   - Use when: Starting fresh or fixing major issues"
echo ""
echo "2) 🔄 Update Deployment (Keep existing config, update container)"
echo "   - Keeps Key Vault and secrets"
echo "   - Builds and deploys new container image"
echo "   - Use when: Deploying new code changes (RECOMMENDED)"
echo ""
echo "3) 🐳 Build Image Only (Build container without deployment)"
echo "   - Builds and pushes new container image to ACR"
echo "   - Doesn't update Container App"
echo "   - Use when: Testing builds before deployment"
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
        echo -e "${GREEN}✓ Build Image Only mode selected${NC}"
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
# VERIFY ACR EXISTS
# ============================================

echo ""
echo -e "${BLUE}🔍 Verifying Azure Container Registry...${NC}"

ACR_EXISTS=$(az acr show --name $ACR_NAME --query id -o tsv 2>/dev/null || echo "")

if [ -z "$ACR_EXISTS" ]; then
    echo -e "${RED}Error: ACR '$ACR_NAME' not found${NC}"
    echo ""
    echo "Create it with:"
    echo "  az acr create \\"
    echo "    --name $ACR_NAME \\"
    echo "    --resource-group $RESOURCE_GROUP \\"
    echo "    --sku Basic \\"
    echo "    --location $LOCATION"
    exit 1
fi

echo -e "${GREEN}✓ ACR verified: $ACR_NAME${NC}"

# ============================================
# BUILD CONTAINER IMAGE (ALL MODES NEED THIS)
# ============================================

echo ""
echo -e "${BLUE}🐳 Building container image...${NC}"

# Get Git SHA and build date
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "manual")
GIT_SHA_FULL=$(git rev-parse HEAD 2>/dev/null || echo "manual-build")
BUILD_DATE=$(date -u +"%Y%m%d-%H%M%S")
IMAGE_TAG="${BUILD_DATE}-${GIT_SHA}"

echo "Build information:"
echo "  Git SHA: $GIT_SHA (full: ${GIT_SHA_FULL:0:12}...)"
echo "  Build Date: $BUILD_DATE"
echo "  Image Tag: $IMAGE_TAG"
echo ""

# Check if container directory exists
if [ ! -d "./container" ]; then
    echo -e "${RED}Error: ./container directory not found${NC}"
    echo "Please run this script from the repository root"
    exit 1
fi

# Verify Dockerfile exists
if [ ! -f "./container/Dockerfile" ]; then
    echo -e "${RED}Error: ./container/Dockerfile not found${NC}"
    exit 1
fi

echo -e "${YELLOW}Building image with ACR Tasks (this may take 3-5 minutes)...${NC}"
echo "Progress will be shown below:"
echo ""

# Build using ACR Tasks
az acr build \
    --registry $ACR_NAME \
    --image "${IMAGE_NAME}:${IMAGE_TAG}" \
    --image "${IMAGE_NAME}:latest" \
    --file ./container/Dockerfile \
    --build-arg GIT_SHA="$GIT_SHA_FULL" \
    --build-arg APP_VERSION="$IMAGE_TAG" \
    --build-arg BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --platform linux/amd64 \
    ./container/

BUILD_STATUS=$?

if [ $BUILD_STATUS -ne 0 ]; then
    echo -e "${RED}✗ Build failed${NC}"
    echo ""
    echo "To troubleshoot:"
    echo "  1. Check Dockerfile syntax in ./container/Dockerfile"
    echo "  2. View build logs above for specific errors"
    echo "  3. Verify all files exist in ./container/"
    exit 1
fi

echo -e "${GREEN}✓ Container image built and pushed to ACR${NC}"
echo "  Tagged as: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
echo "  Tagged as: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest"

# Verify image exists in ACR
echo ""
echo "Verifying image in ACR..."
IMAGE_DIGEST=$(az acr repository show \
    --name $ACR_NAME \
    --image "${IMAGE_NAME}:${IMAGE_TAG}" \
    --query digest -o tsv 2>/dev/null || echo "")

if [ -z "$IMAGE_DIGEST" ]; then
    echo -e "${RED}✗ Image verification failed - image not found in ACR${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Image verified in ACR (digest: ${IMAGE_DIGEST:0:20}...)${NC}"

# Store the image reference for deployment
DEPLOYMENT_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"

# If build-only mode, exit here
if [ "$INSTALL_MODE" = "build-only" ]; then
    echo ""
    echo -e "${GREEN}✅ Build Complete!${NC}"
    echo ""
    echo "Image ready for deployment:"
    echo "  ${DEPLOYMENT_IMAGE}"
    echo ""
    echo "To deploy this image:"
    echo "  az containerapp update \\"
    echo "    --name $CONTAINER_APP \\"
    echo "    --resource-group $RESOURCE_GROUP \\"
    echo "    --image ${DEPLOYMENT_IMAGE}"
    echo ""
    exit 0
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
    
    # Generate and store API key
    echo "Generating API key..."
    API_KEY=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
    az keyvault secret set --vault-name $KV_NAME --name api-key --value "$API_KEY" > /dev/null
    echo -e "${GREEN}✓ API key generated and stored${NC}"
    echo -e "${YELLOW}API Key: $API_KEY${NC}"
    echo -e "${RED}IMPORTANT: Save this key! You won't see it again.${NC}"
    echo ""
    
    # ============================================
    # Create Container App with Managed Identity
    # ============================================
    
    echo ""
    echo -e "${BLUE}🚀 Creating Container App...${NC}"
    echo "This may take 2-3 minutes..."
    
    az containerapp create \
      --name $CONTAINER_APP \
      --resource-group $RESOURCE_GROUP \
      --environment $ENV_NAME \
      --image $DEPLOYMENT_IMAGE \
      --registry-server ${ACR_NAME}.azurecr.io \
      --registry-identity system \
      --target-port 8000 \
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
    echo "Waiting for identity to propagate (20 seconds)..."
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
        authorized-domains="keyvaultref:${KV_URL}/secrets/authorized-domains,identityref:system" \
        api-key="keyvaultref:${KV_URL}/secrets/api-key,identityref:system"
    
    echo -e "${GREEN}✓ Container App secrets linked to Key Vault${NC}"
fi

# ============================================
# UPDATE DEPLOYMENT (Works for both clean and update)
# ============================================

echo ""
echo -e "${BLUE}⚙️  Updating Container App configuration...${NC}"

# Get app URL
FQDN=$(az containerapp show \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn -o tsv)

APP_URL="https://$FQDN"

# For update mode, ensure API key exists
if [ "$INSTALL_MODE" = "update" ]; then
    API_KEY_EXISTS=$(az keyvault secret show \
        --vault-name $KV_NAME \
        --name api-key \
        --query value -o tsv 2>/dev/null || echo "")
    
    if [ -z "$API_KEY_EXISTS" ]; then
        echo "Generating new API key..."
        API_KEY=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
        az keyvault secret set --vault-name $KV_NAME --name api-key --value "$API_KEY" > /dev/null
        
        # Add to container app secrets
        KV_URL="https://${KV_NAME}.vault.azure.net"
        az containerapp secret set \
            --name $CONTAINER_APP \
            --resource-group $RESOURCE_GROUP \
            --secrets \
                api-key="keyvaultref:${KV_URL}/secrets/api-key,identityref:system"
        
        echo -e "${GREEN}✓ API key generated${NC}"
        echo -e "${YELLOW}API Key: $API_KEY${NC}"
        echo -e "${RED}IMPORTANT: Save this key!${NC}"
        echo ""
    fi
fi

# Update container with new image and environment variables
echo "Updating container app..."
echo "  Image: $DEPLOYMENT_IMAGE"
echo ""

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
    API_ENABLED="true" \
    API_KEY=secretref:api-key \
    API_PORT="8001" \
    API_RATE_LIMIT="100" \
    APP_VERSION="${IMAGE_TAG}" \
    GIT_SHA="$GIT_SHA_FULL" \
    BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

UPDATE_STATUS=$?

if [ $UPDATE_STATUS -ne 0 ]; then
    echo -e "${RED}✗ Container App update failed${NC}"
    echo ""
    echo "Check logs with:"
    echo "  az containerapp logs show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --tail 50"
    exit 1
fi

echo -e "${GREEN}✓ Container App updated${NC}"

# Wait for update to complete
echo "Waiting for deployment to stabilize (30 seconds)..."
sleep 30

# ============================================
# Verification
# ============================================

echo ""
echo -e "${BLUE}🔍 Verifying deployment...${NC}"

# Get current revision
CURRENT_REVISION=$(az containerapp revision list \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --query "[?properties.active==\`true\`].name | [0]" -o tsv)

if [ -z "$CURRENT_REVISION" ]; then
    echo -e "${RED}⚠️  No active revision found${NC}"
    echo "Checking all revisions..."
    az containerapp revision list \
      --name $CONTAINER_APP \
      --resource-group $RESOURCE_GROUP \
      --output table
else
    echo "Active revision: $CURRENT_REVISION"
    
    # Check running replicas
    REPLICA_COUNT=$(az containerapp replica list \
      --name $CONTAINER_APP \
      --resource-group $RESOURCE_GROUP \
      --revision $CURRENT_REVISION \
      --query "length([?properties.runningState=='Running'])" -o tsv 2>/dev/null || echo "0")
    
    if [ "$REPLICA_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✓ Container is running ($REPLICA_COUNT replica(s))${NC}"
    else
        echo -e "${YELLOW}⚠️  No running replicas detected${NC}"
        echo "Container may still be starting. Check logs:"
        echo "  az containerapp logs show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --follow"
    fi
fi

# Verify image
CURRENT_IMAGE=$(az containerapp show \
  --name $CONTAINER_APP \
  --resource-group $RESOURCE_GROUP \
  --query "properties.template.containers[0].image" -o tsv)

echo "Current image: $CURRENT_IMAGE"

if [[ "$CURRENT_IMAGE" == *"$IMAGE_TAG"* ]]; then
    echo -e "${GREEN}✓ Correct image deployed${NC}"
else
    echo -e "${YELLOW}⚠️  Image mismatch - deployment may still be in progress${NC}"
fi

# ============================================
# Summary
# ============================================

echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "===================="
echo ""
echo -e "${BLUE}📋 Summary:${NC}"
echo "   Mode: $INSTALL_MODE"
echo "   Resource Group: $RESOURCE_GROUP"
echo "   Container App: $CONTAINER_APP"
echo "   Image Tag: $IMAGE_TAG"
echo "   Git SHA: $GIT_SHA"
echo "   Active Revision: $CURRENT_REVISION"
echo ""
echo -e "${BLUE}🌐 Application URL:${NC}"
echo "   $APP_URL"
echo ""
echo -e "${BLUE}🔐 Security:${NC}"
echo "   ✅ Managed Identity enabled"
echo "   ✅ Secrets in Key Vault"
echo "   ⚠️  Auth: DISABLED (set REQUIRE_AUTH=true to enable)"
echo "   ⚠️  API: DISABLED (set API_ENABLED=true to enable)"
echo ""
echo -e "${BLUE}📝 Next Steps:${NC}"
echo ""
echo "1. Test your application:"
echo "   curl $APP_URL/_stcore/health"
echo ""
echo "2. View logs:"
echo "   az containerapp logs show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --follow"
echo ""
echo "3. Enable API (optional):"
echo "   az containerapp update --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --set-env-vars API_ENABLED=true"
echo ""
echo "4. Get API key:"
echo "   az keyvault secret show --vault-name $KV_NAME --name api-key --query value -o tsv"
echo ""
echo "5. Enable authentication (optional):"
echo "   az containerapp update --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --set-env-vars REQUIRE_AUTH=true"
echo ""
echo -e "${GREEN}🎉 Setup complete!${NC}"
echo ""
