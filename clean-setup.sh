#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}🛡️  Threat Modeling Application Setup${NC}"
echo -e "${BLUE}   (Azure Cloud Shell Compatible)${NC}"
echo "=============================================="
echo ""

# ============================================
# STATIC CONFIGURATION
# ============================================

RESOURCE_GROUP="threat-modeling-poc"
LOCATION="australiaeast"
KV_NAME="threat-modeling-kv"
CONTAINER_APP="threat-modeling"
ENV_NAME="threat-modeling-env"
ACR_NAME="threatmodelingacr"
IMAGE_NAME="threat-modeling"

# ============================================
# INSTALLATION MODE SELECTION
# ============================================

echo -e "${YELLOW}Select installation mode:${NC}"
echo ""
echo "1) 🆕 Clean Install — delete everything and start fresh"
echo "2) 🔄 Update Deployment — keep config, deploy new container image"
echo "3) 🔑 Update Secrets Only — update Key Vault secrets and restart"
echo "4) 🐳 Build & Push Only — build image without deploying"
echo ""
read -p "Enter choice [1-4]: " MODE

case $MODE in
    1) INSTALL_MODE="clean";      echo -e "${GREEN}✓ Clean Install${NC}" ;;
    2) INSTALL_MODE="update";     echo -e "${GREEN}✓ Update Deployment${NC}" ;;
    3) INSTALL_MODE="secrets";    echo -e "${GREEN}✓ Update Secrets Only${NC}" ;;
    4) INSTALL_MODE="build-only"; echo -e "${GREEN}✓ Build & Push Only${NC}" ;;
    *) echo -e "${RED}Invalid choice.${NC}"; exit 1 ;;
esac

# ============================================
# COLLECT SECRETS INTERACTIVELY
# Only prompt when needed for the selected mode
# ============================================

collect_secrets() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  🔐 Secret Configuration${NC}"
    echo -e "${CYAN}  Tip: press Enter to keep existing value in Key Vault${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # ── Azure OpenAI ──────────────────────────────────────────────────────────

    echo -e "${BLUE}Azure OpenAI${NC}"
    echo "  Find these in: Azure Portal → Azure OpenAI → your resource → Keys and Endpoint"
    echo ""

    # Show current value hint if Key Vault exists
    CURRENT_ENDPOINT=$(az keyvault secret show --vault-name "$KV_NAME" --name azure-openai-endpoint \
        --query value -o tsv 2>/dev/null || echo "")
    if [ -n "$CURRENT_ENDPOINT" ]; then
        echo -e "  Current endpoint: ${YELLOW}${CURRENT_ENDPOINT}${NC}"
    fi
    read -p "  Azure OpenAI Endpoint (e.g. https://myresource.openai.azure.com/): " INPUT_ENDPOINT
    OPENAI_ENDPOINT="${INPUT_ENDPOINT:-$CURRENT_ENDPOINT}"
    if [ -z "$OPENAI_ENDPOINT" ]; then
        echo -e "${RED}  ✗ Endpoint is required${NC}"; exit 1
    fi

    read -s -p "  Azure OpenAI API Key (input hidden): " INPUT_KEY
    echo ""
    if [ -z "$INPUT_KEY" ]; then
        CURRENT_KEY=$(az keyvault secret show --vault-name "$KV_NAME" --name azure-openai-key \
            --query value -o tsv 2>/dev/null || echo "")
        OPENAI_KEY="${CURRENT_KEY}"
        if [ -z "$OPENAI_KEY" ]; then
            echo -e "${RED}  ✗ API Key is required${NC}"; exit 1
        fi
        echo "  Using existing key from Key Vault"
    else
        OPENAI_KEY="$INPUT_KEY"
    fi

    CURRENT_DEPLOYMENT=$(az keyvault secret show --vault-name "$KV_NAME" --name azure-openai-deployment \
        --query value -o tsv 2>/dev/null || echo "gpt-4o")
    read -p "  Deployment name [${CURRENT_DEPLOYMENT}]: " INPUT_DEPLOYMENT
    OPENAI_DEPLOYMENT="${INPUT_DEPLOYMENT:-$CURRENT_DEPLOYMENT}"

    CURRENT_API_VERSION=$(az keyvault secret show --vault-name "$KV_NAME" --name azure-openai-api-version \
        --query value -o tsv 2>/dev/null || echo "2024-02-01")
    read -p "  API Version [${CURRENT_API_VERSION}]: " INPUT_VERSION
    OPENAI_API_VERSION="${INPUT_VERSION:-$CURRENT_API_VERSION}"

    echo ""
    echo -e "${BLUE}Google OAuth  ${YELLOW}(press Enter to skip / keep existing)${NC}"
    echo "  Find these in: console.cloud.google.com → APIs & Services → Credentials"
    echo ""

    CURRENT_GID=$(az keyvault secret show --vault-name "$KV_NAME" --name google-client-id \
        --query value -o tsv 2>/dev/null || echo "")
    if [ -n "$CURRENT_GID" ]; then
        echo -e "  Current Client ID: ${YELLOW}${CURRENT_GID:0:20}...${NC}"
    fi
    read -p "  Google Client ID: " INPUT_GID
    GOOGLE_CLIENT_ID="${INPUT_GID:-$CURRENT_GID}"

    read -s -p "  Google Client Secret (input hidden): " INPUT_GSECRET
    echo ""
    if [ -z "$INPUT_GSECRET" ]; then
        CURRENT_GSECRET=$(az keyvault secret show --vault-name "$KV_NAME" --name google-client-secret \
            --query value -o tsv 2>/dev/null || echo "")
        GOOGLE_CLIENT_SECRET="${CURRENT_GSECRET}"
    else
        GOOGLE_CLIENT_SECRET="$INPUT_GSECRET"
    fi

    CURRENT_DOMAINS=$(az keyvault secret show --vault-name "$KV_NAME" --name authorized-domains \
        --query value -o tsv 2>/dev/null || echo "gmail.com")
    read -p "  Authorized email domains [${CURRENT_DOMAINS}]: " INPUT_DOMAINS
    AUTHORIZED_DOMAINS="${INPUT_DOMAINS:-$CURRENT_DOMAINS}"

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${GREEN}Secrets collected:${NC}"
    echo "    OpenAI Endpoint : $OPENAI_ENDPOINT"
    echo "    OpenAI Key      : ${OPENAI_KEY:0:8}••••••••"
    echo "    Deployment      : $OPENAI_DEPLOYMENT"
    echo "    API Version     : $OPENAI_API_VERSION"
    if [ -n "$GOOGLE_CLIENT_ID" ]; then
        echo "    Google Client ID: ${GOOGLE_CLIENT_ID:0:20}..."
    else
        echo "    Google OAuth    : not configured"
    fi
    echo "    Auth Domains    : $AUTHORIZED_DOMAINS"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    read -p "Proceed with these values? (yes/no): " CONFIRM_SECRETS
    if [ "$CONFIRM_SECRETS" != "yes" ]; then
        echo "Cancelled."; exit 0
    fi
}

push_secrets_to_keyvault() {
    echo ""
    echo -e "${BLUE}🔒 Storing secrets in Key Vault...${NC}"

    az keyvault secret set --vault-name "$KV_NAME" --name azure-openai-key      --value "$OPENAI_KEY"        > /dev/null
    az keyvault secret set --vault-name "$KV_NAME" --name azure-openai-endpoint  --value "$OPENAI_ENDPOINT"   > /dev/null
    az keyvault secret set --vault-name "$KV_NAME" --name azure-openai-deployment --value "$OPENAI_DEPLOYMENT" > /dev/null
    az keyvault secret set --vault-name "$KV_NAME" --name azure-openai-api-version --value "$OPENAI_API_VERSION" > /dev/null
    echo -e "  ${GREEN}✓ Azure OpenAI secrets stored${NC}"

    if [ -n "$GOOGLE_CLIENT_ID" ]; then
        az keyvault secret set --vault-name "$KV_NAME" --name google-client-id     --value "$GOOGLE_CLIENT_ID"     > /dev/null
        az keyvault secret set --vault-name "$KV_NAME" --name google-client-secret --value "$GOOGLE_CLIENT_SECRET" > /dev/null
        echo -e "  ${GREEN}✓ Google OAuth secrets stored${NC}"
    fi
    az keyvault secret set --vault-name "$KV_NAME" --name authorized-domains --value "$AUTHORIZED_DOMAINS" > /dev/null
    echo -e "  ${GREEN}✓ Authorized domains stored${NC}"
}

restart_container() {
    echo ""
    echo -e "${BLUE}🔄 Restarting container app to pick up new secrets...${NC}"

    CURRENT_REVISION=$(az containerapp revision list \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query "[?properties.active==\`true\`].name | [0]" -o tsv 2>/dev/null || echo "")

    if [ -n "$CURRENT_REVISION" ]; then
        az containerapp revision restart \
            --name "$CONTAINER_APP" \
            --resource-group "$RESOURCE_GROUP" \
            --revision "$CURRENT_REVISION"
        echo -e "  ${GREEN}✓ Revision '$CURRENT_REVISION' restarted${NC}"
    else
        echo -e "  ${YELLOW}⚠ No active revision found — forcing update to trigger restart${NC}"
        az containerapp update \
            --name "$CONTAINER_APP" \
            --resource-group "$RESOURCE_GROUP" \
            --set-env-vars LAST_RESTART="$(date -u +%Y%m%dT%H%M%SZ)"
    fi

    echo "  Waiting 20s for restart..."
    sleep 20
}

# ============================================
# SECRETS-ONLY MODE
# ============================================

if [ "$INSTALL_MODE" = "secrets" ]; then
    echo ""
    echo -e "${YELLOW}This will update secrets in Key Vault and restart the container.${NC}"
    echo ""
    collect_secrets
    push_secrets_to_keyvault
    restart_container

    FQDN=$(az containerapp show \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null || echo "unknown")

    echo ""
    echo -e "${GREEN}✅ Secrets updated and container restarted!${NC}"
    echo "   App URL: https://$FQDN"
    echo ""
    echo -e "${BLUE}Verify the fix:${NC}"
    echo "  az containerapp logs show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --tail 30"
    exit 0
fi

# ============================================
# CONFIRM CONFIG SUMMARY (non-secrets modes)
# ============================================

echo ""
echo -e "${BLUE}📋 Configuration:${NC}"
echo "   Resource Group : $RESOURCE_GROUP"
echo "   Location       : $LOCATION"
echo "   Key Vault      : $KV_NAME"
echo "   Container App  : $CONTAINER_APP"
echo "   ACR            : $ACR_NAME"
echo "   Mode           : $INSTALL_MODE"
echo ""
read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then echo "Cancelled."; exit 0; fi

# ============================================
# BUILD & PUSH
# ============================================

if [ "$INSTALL_MODE" != "clean" ]; then
    echo ""
    echo -e "${BLUE}🐳 Building container image via ACR Tasks...${NC}"

    GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "local")
    BUILD_DATE=$(date -u +"%Y%m%d-%H%M%S")
    IMAGE_TAG="${BUILD_DATE}-${GIT_SHA}"

    if [ ! -d "./container" ]; then
        echo -e "${RED}Error: ./container directory not found — run from repo root${NC}"; exit 1
    fi

    az acr build \
        --registry "$ACR_NAME" \
        --image "${IMAGE_NAME}:${IMAGE_TAG}" \
        --image "${IMAGE_NAME}:latest" \
        --file ./container/Dockerfile \
        --build-arg GIT_SHA="$GIT_SHA" \
        --build-arg APP_VERSION="$IMAGE_TAG" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        ./container/

    echo -e "${GREEN}✓ Image built: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}${NC}"
    DEPLOYMENT_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"

    if [ "$INSTALL_MODE" = "build-only" ]; then
        echo ""
        echo -e "${GREEN}✅ Build complete.${NC}"
        echo "Deploy with:"
        echo "  az containerapp update --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --image $DEPLOYMENT_IMAGE"
        exit 0
    fi
else
    DEPLOYMENT_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest"
fi

# ============================================
# CLEAN INSTALL
# ============================================

if [ "$INSTALL_MODE" = "clean" ]; then

    collect_secrets

    echo ""
    echo -e "${YELLOW}🗑️  Cleaning up existing resources...${NC}"
    az containerapp delete --name "$CONTAINER_APP" --resource-group "$RESOURCE_GROUP" --yes 2>/dev/null \
        && echo -e "  ${GREEN}✓ Container App deleted${NC}" || echo "  ✓ No Container App to delete"
    az keyvault delete --name "$KV_NAME" --resource-group "$RESOURCE_GROUP" 2>/dev/null \
        && echo -e "  ${GREEN}✓ Key Vault deleted${NC}" || echo "  ✓ No Key Vault to delete"
    az keyvault purge --name "$KV_NAME" --no-wait 2>/dev/null \
        && echo -e "  ${GREEN}✓ Key Vault purged${NC}" || echo "  ✓ No Key Vault to purge"
    echo "  Waiting 30s for cleanup..."
    sleep 30

    # Create Key Vault
    echo ""
    echo -e "${BLUE}🔐 Creating Key Vault...${NC}"
    az keyvault create \
        --name "$KV_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --enable-rbac-authorization false \
        --enabled-for-deployment true \
        --enabled-for-template-deployment true
    echo -e "  ${GREEN}✓ Key Vault created${NC}"

    push_secrets_to_keyvault

    # Generate API key
    API_KEY=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
    az keyvault secret set --vault-name "$KV_NAME" --name api-key --value "$API_KEY" > /dev/null
    echo -e "  ${GREEN}✓ API key generated${NC}"
    echo -e "  ${YELLOW}API Key: $API_KEY${NC}"
    echo -e "  ${RED}IMPORTANT: Save this key — you won't see it again.${NC}"

    # Build initial image
    echo ""
    echo -e "${BLUE}🐳 Building initial container image...${NC}"
    IMAGE_EXISTS=$(az acr repository show --name "$ACR_NAME" --repository "$IMAGE_NAME" \
        --query "name" -o tsv 2>/dev/null || echo "")
    if [ -z "$IMAGE_EXISTS" ]; then
        GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "initial")
        BUILD_DATE=$(date -u +"%Y%m%d-%H%M%S")
        az acr build \
            --registry "$ACR_NAME" \
            --image "${IMAGE_NAME}:latest" \
            --image "${IMAGE_NAME}:initial" \
            --file ./container/Dockerfile \
            --build-arg GIT_SHA="$GIT_SHA" \
            --build-arg APP_VERSION="initial" \
            --build-arg BUILD_DATE="$BUILD_DATE" \
            ./container/
        echo -e "  ${GREEN}✓ Initial image built${NC}"
    else
        echo -e "  ${GREEN}✓ Image already exists in ACR${NC}"
    fi

    # Create Container App
    echo ""
    echo -e "${BLUE}🚀 Creating Container App...${NC}"
    az containerapp create \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --environment "$ENV_NAME" \
        --image "$DEPLOYMENT_IMAGE" \
        --registry-server "${ACR_NAME}.azurecr.io" \
        --registry-identity system \
        --target-port 8000 \
        --ingress external \
        --cpu 1.0 \
        --memory 2.0Gi \
        --min-replicas 1 \
        --max-replicas 3 \
        --system-assigned
    echo -e "  ${GREEN}✓ Container App created${NC}"

    # Grant permissions
    echo ""
    echo -e "${BLUE}🔓 Granting permissions...${NC}"
    PRINCIPAL_ID=$(az containerapp show \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query identity.principalId -o tsv)
    echo "  Waiting 20s for managed identity to propagate..."
    sleep 20

    az keyvault set-policy \
        --name "$KV_NAME" \
        --object-id "$PRINCIPAL_ID" \
        --secret-permissions get list
    echo -e "  ${GREEN}✓ Key Vault access granted${NC}"

    ACR_ID=$(az acr show --name "$ACR_NAME" --query id -o tsv)
    az role assignment create --assignee "$PRINCIPAL_ID" --role AcrPull --scope "$ACR_ID" 2>/dev/null \
        && echo -e "  ${GREEN}✓ ACR pull access granted${NC}" \
        || echo -e "  ${GREEN}✓ ACR pull access already exists${NC}"

    # Link secrets
    echo ""
    echo -e "${BLUE}🔗 Linking Container App to Key Vault...${NC}"
    KV_URL="https://${KV_NAME}.vault.azure.net"
    az containerapp secret set \
        --name "$CONTAINER_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --secrets \
            azure-openai-endpoint="keyvaultref:${KV_URL}/secrets/azure-openai-endpoint,identityref:system" \
            azure-openai-key="keyvaultref:${KV_URL}/secrets/azure-openai-key,identityref:system" \
            azure-openai-deployment="keyvaultref:${KV_URL}/secrets/azure-openai-deployment,identityref:system" \
            azure-openai-api-version="keyvaultref:${KV_URL}/secrets/azure-openai-api-version,identityref:system" \
            google-client-id="keyvaultref:${KV_URL}/secrets/google-client-id,identityref:system" \
            google-client-secret="keyvaultref:${KV_URL}/secrets/google-client-secret,identityref:system" \
            authorized-domains="keyvaultref:${KV_URL}/secrets/authorized-domains,identityref:system" \
            api-key="keyvaultref:${KV_URL}/secrets/api-key,identityref:system"
    echo -e "  ${GREEN}✓ Secrets linked to Key Vault${NC}"
fi

# ============================================
# UPDATE / DEPLOY CONTAINER
# ============================================

echo ""
echo -e "${BLUE}⚙️  Updating Container App...${NC}"

FQDN=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn -o tsv)
APP_URL="https://$FQDN"

GIT_SHA_FULL=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

az containerapp update \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$DEPLOYMENT_IMAGE" \
    --set-env-vars \
        AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
        AZURE_OPENAI_KEY=secretref:azure-openai-key \
        AZURE_OPENAI_DEPLOYMENT=secretref:azure-openai-deployment \
        AZURE_OPENAI_API_VERSION=secretref:azure-openai-api-version \
        REQUIRE_AUTH="false" \
        APP_URL="$APP_URL" \
        GOOGLE_CLIENT_ID=secretref:google-client-id \
        GOOGLE_CLIENT_SECRET=secretref:google-client-secret \
        AUTHORIZED_DOMAINS=secretref:authorized-domains \
        API_ENABLED="false" \
        API_KEY=secretref:api-key \
        API_PORT="8001" \
        API_RATE_LIMIT="100" \
        APP_VERSION="${IMAGE_TAG:-latest}" \
        GIT_SHA="$GIT_SHA_FULL" \
        BUILD_DATE="$BUILD_DATE"

echo -e "  ${GREEN}✓ Container App updated${NC}"

restart_container

# ============================================
# VERIFY
# ============================================

echo ""
echo -e "${BLUE}🔍 Verifying deployment...${NC}"

CURRENT_REVISION=$(az containerapp revision list \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?properties.active==\`true\`].name | [0]" -o tsv 2>/dev/null || echo "")

REPLICA_COUNT=$(az containerapp replica list \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --revision "$CURRENT_REVISION" \
    --query "length([?properties.runningState=='Running'])" -o tsv 2>/dev/null || echo "0")

if [ "$REPLICA_COUNT" -gt 0 ]; then
    echo -e "  ${GREEN}✓ $REPLICA_COUNT replica(s) running${NC}"
else
    echo -e "  ${RED}⚠ No running replicas — checking logs:${NC}"
    az containerapp logs show --name "$CONTAINER_APP" --resource-group "$RESOURCE_GROUP" --tail 20 2>/dev/null || true
fi

CURRENT_IMAGE=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.template.containers[0].image" -o tsv)

# ============================================
# SUMMARY
# ============================================

echo ""
echo -e "${GREEN}✅ Done!${NC}"
echo "══════════════════════════════════════════════"
echo ""
echo -e "${BLUE}Summary${NC}"
echo "  Mode          : $INSTALL_MODE"
echo "  Container App : $CONTAINER_APP"
echo "  Image         : $CURRENT_IMAGE"
echo "  Revision      : $CURRENT_REVISION"
echo "  URL           : $APP_URL"
echo ""
echo -e "${BLUE}Useful commands${NC}"
echo "  # View live logs"
echo "  az containerapp logs show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --follow"
echo ""
echo "  # Update a single secret"
echo "  az keyvault secret set --vault-name $KV_NAME --name azure-openai-key --value NEW_VALUE"
echo "  # Then restart:"
echo "  az containerapp revision restart --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --revision \$(az containerapp revision list --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --query \"[?properties.active==\\\`true\\\`].name|[0]\" -o tsv)"
echo ""
echo "  # Enable OAuth"
echo "  az containerapp update --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --set-env-vars REQUIRE_AUTH=true"
echo ""

if [ "$INSTALL_MODE" = "clean" ]; then
    echo -e "${YELLOW}⚠ Update your Google OAuth redirect URI to: $APP_URL/${NC}"
    echo "  https://console.cloud.google.com/apis/credentials"
    echo ""
fi

echo -e "${GREEN}🎉 Application ready at $APP_URL${NC}"
echo ""
