#!/bin/bash
set -e

echo "🔐 Setting up GitHub OIDC for Passwordless Authentication"
echo "=========================================================="
echo ""
echo "This eliminates ALL passwords from GitHub!"
echo ""

# Configuration
RESOURCE_GROUP="threat-modeling-poc"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
APP_NAME="github-actions-threat-modeling"

# GitHub repository info - UPDATE THESE
GITHUB_ORG="swift-mammoth"
GITHUB_REPO="threat-modelling-poc"

echo "📋 Configuration:"
echo "   Subscription: $SUBSCRIPTION_ID"
echo "   Resource Group: $RESOURCE_GROUP"
echo "   App Name: $APP_NAME"
echo "   GitHub Repo: $GITHUB_ORG/$GITHUB_REPO"
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# ============================================
# Step 1: Create or Get Azure AD Application
# ============================================

echo ""
echo "📱 Step 1: Checking Azure AD Application..."

# Check if app already exists
EXISTING_APP=$(az ad app list --display-name $APP_NAME --query "[0].appId" -o tsv)

if [ -n "$EXISTING_APP" ]; then
    echo "✓ Application already exists"
    APP_ID=$EXISTING_APP
    echo "App ID: $APP_ID"
else
    echo "Creating new application..."
    APP_ID=$(az ad app create \
      --display-name $APP_NAME \
      --query appId -o tsv)
    echo "✓ App ID: $APP_ID"
fi

# Check if service principal exists
EXISTING_SP=$(az ad sp list --display-name $APP_NAME --query "[0].id" -o tsv)

if [ -n "$EXISTING_SP" ]; then
    echo "✓ Service principal already exists"
    SP_ID=$EXISTING_SP
else
    echo "Creating service principal..."
    SP_ID=$(az ad sp create --id $APP_ID --query id -o tsv)
    echo "✓ Service Principal ID: $SP_ID"
    
    # Wait for propagation only if newly created
    echo "Waiting for service principal to propagate..."
    sleep 10
fi

# ============================================
# Step 2: Assign Permissions
# ============================================

echo ""
echo "🔓 Step 2: Assigning Azure permissions..."

# Grant Contributor on resource group
echo "Checking Contributor role..."
EXISTING_ROLE=$(az role assignment list \
  --assignee $APP_ID \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --query "[0].id" -o tsv)

if [ -n "$EXISTING_ROLE" ]; then
    echo "✓ Contributor role already assigned"
else
    echo "Assigning Contributor role..."
    az role assignment create \
      --assignee $APP_ID \
      --role Contributor \
      --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP
    echo "✓ Contributor role assigned"
fi

# Grant AcrPush on ACR
echo "Checking AcrPush role..."
ACR_ID=$(az acr show --name threatmodelingacr --query id -o tsv)
EXISTING_ACR_ROLE=$(az role assignment list \
  --assignee $APP_ID \
  --role AcrPush \
  --scope $ACR_ID \
  --query "[0].id" -o tsv)

if [ -n "$EXISTING_ACR_ROLE" ]; then
    echo "✓ AcrPush role already assigned"
else
    echo "Assigning AcrPush role..."
    az role assignment create \
      --assignee $APP_ID \
      --role AcrPush \
      --scope $ACR_ID
    echo "✓ AcrPush role assigned"
fi

# ============================================
# Step 3: Configure Federated Credentials
# ============================================

echo ""
echo "🔗 Step 3: Configuring GitHub OIDC federated credentials..."

# Check existing federated credentials
EXISTING_CREDS=$(az ad app federated-credential list --id $APP_ID --query "[].name" -o tsv)

# For main branch
if echo "$EXISTING_CREDS" | grep -q "github-main"; then
    echo "✓ Federated credential for main branch already exists"
else
    echo "Creating federated credential for main branch..."
    cat > credential-main.json <<EOF
{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main",
  "description": "GitHub Actions - main branch",
  "audiences": [
    "api://AzureADTokenExchange"
  ]
}
EOF

    az ad app federated-credential create \
      --id $APP_ID \
      --parameters credential-main.json

    echo "✓ Federated credential for main branch created"
    rm credential-main.json
fi

# For pull requests
if echo "$EXISTING_CREDS" | grep -q "github-pr"; then
    echo "✓ Federated credential for pull requests already exists"
else
    echo "Creating federated credential for pull requests..."
    cat > credential-pr.json <<EOF
{
  "name": "github-pr",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${GITHUB_ORG}/${GITHUB_REPO}:pull_request",
  "description": "GitHub Actions - pull requests",
  "audiences": [
    "api://AzureADTokenExchange"
  ]
}
EOF

    az ad app federated-credential create \
      --id $APP_ID \
      --parameters credential-pr.json

    echo "✓ Federated credential for pull requests created"
    rm credential-pr.json
fi

# ============================================
# Step 4: Summary
# ============================================

TENANT_ID=$(az account show --query tenantId -o tsv)

echo ""
echo "✅ GitHub OIDC Setup Complete!"
echo "================================"
echo ""
echo "📋 Add these secrets to GitHub:"
echo ""
echo "Secret Name: AZURE_CLIENT_ID"
echo "Value: $APP_ID"
echo ""
echo "Secret Name: AZURE_TENANT_ID"
echo "Value: $TENANT_ID"
echo ""
echo "Secret Name: AZURE_SUBSCRIPTION_ID"
echo "Value: $SUBSCRIPTION_ID"
echo ""
echo "⚠️  NO PASSWORD NEEDED! ✨"
echo ""
echo "🔗 Add secrets at:"
echo "   https://github.com/$GITHUB_ORG/$GITHUB_REPO/settings/secrets/actions"
echo ""
echo "📝 Update your workflow to use:"
echo "   - azure/login@v1 with client-id, tenant-id, subscription-id"
echo "   See: .github/workflows/security-deploy-oidc.yml"
echo ""
echo "🗑️  You can now remove from GitHub:"
echo "   - AZURE_CREDENTIALS (old service principal)"
echo "   - ACR_USERNAME"
echo "   - ACR_PASSWORD"
echo ""
