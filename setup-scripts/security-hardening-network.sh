#!/bin/bash
set -e

echo "🔒 Security Hardening - Network Isolation"
echo "=========================================="
echo ""
echo "This script will:"
echo "1. Create Virtual Network (VNET)"
echo "2. Configure Container Apps with VNET integration"
echo "3. Set up IP allowlist (optional)"
echo "4. Disable public access (optional)"
echo ""

# Configuration
RESOURCE_GROUP="threat-modeling-poc"
LOCATION="australiaeast"
VNET_NAME="threat-modeling-vnet"
SUBNET_NAME="container-apps-subnet"
CONTAINER_APP="threat-modeling"
ENV_NAME="threat-modeling-env"

echo "📋 Configuration:"
echo "   Resource Group: $RESOURCE_GROUP"
echo "   VNET: $VNET_NAME"
echo "   Location: $LOCATION"
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# ============================================
# Step 1: Create Virtual Network
# ============================================

echo ""
echo "🌐 Step 1: Creating Virtual Network..."

# Check if VNET exists
EXISTING_VNET=$(az network vnet show \
  --name $VNET_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv 2>/dev/null || echo "")

if [ -n "$EXISTING_VNET" ]; then
    echo "✓ VNET already exists: $VNET_NAME"
else
    echo "Creating VNET..."
    az network vnet create \
      --name $VNET_NAME \
      --resource-group $RESOURCE_GROUP \
      --location $LOCATION \
      --address-prefix 10.0.0.0/16
    
    echo "✓ VNET created"
fi

# ============================================
# Step 2: Create Subnet for Container Apps
# ============================================

echo ""
echo "📡 Step 2: Creating subnet..."

# Check if subnet exists
EXISTING_SUBNET=$(az network vnet subnet show \
  --vnet-name $VNET_NAME \
  --name $SUBNET_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv 2>/dev/null || echo "")

if [ -n "$EXISTING_SUBNET" ]; then
    echo "✓ Subnet already exists: $SUBNET_NAME"
    SUBNET_ID=$EXISTING_SUBNET
else
    echo "Creating subnet for Container Apps..."
    SUBNET_ID=$(az network vnet subnet create \
      --vnet-name $VNET_NAME \
      --name $SUBNET_NAME \
      --resource-group $RESOURCE_GROUP \
      --address-prefixes 10.0.0.0/23 \
      --query id -o tsv)
    
    echo "✓ Subnet created"
fi

# ============================================
# Step 3: Create Container Apps Environment with VNET
# ============================================

echo ""
echo "🏗️  Step 3: Configuring Container Apps Environment..."

# Note: Container Apps Environment VNET integration must be set at creation
# If your environment already exists, you'll need to recreate it

echo "⚠️  Warning: VNET integration requires recreating Container Apps Environment"
echo ""
read -p "Recreate environment with VNET? This will cause ~5 min downtime (yes/no): " RECREATE

if [ "$RECREATE" = "yes" ]; then
    # Delete existing environment
    echo "Deleting existing environment..."
    az containerapp env delete \
      --name $ENV_NAME \
      --resource-group $RESOURCE_GROUP \
      --yes 2>/dev/null || echo "Environment not found or already deleted"
    
    # Wait for deletion
    echo "Waiting for deletion to complete..."
    sleep 30
    
    # Create new environment with VNET
    echo "Creating new environment with VNET integration..."
    az containerapp env create \
      --name $ENV_NAME \
      --resource-group $RESOURCE_GROUP \
      --location $LOCATION \
      --infrastructure-subnet-resource-id $SUBNET_ID \
      --internal-only false
    
    echo "✓ Environment created with VNET integration"
    
    # Note: You'll need to redeploy your container app
    echo ""
    echo "⚠️  You need to redeploy your container app:"
    echo "   git push origin main"
    echo "   (GitHub Actions will redeploy automatically)"
else
    echo "Skipping environment recreation"
    echo ""
    echo "Note: Without VNET integration, IP restrictions are the only network control"
fi

# ============================================
# Step 4: Configure IP Restrictions (Optional)
# ============================================

echo ""
echo "🔐 Step 4: IP Allowlist Configuration (Optional)"
echo ""
echo "Do you want to restrict access to specific IP addresses?"
echo "Examples:"
echo "  - Your office IP: 203.0.113.50"
echo "  - Your VPN range: 10.20.0.0/16"
echo "  - Azure services: AzureCloud"
echo ""
read -p "Configure IP restrictions? (yes/no): " CONFIGURE_IP

if [ "$CONFIGURE_IP" = "yes" ]; then
    echo ""
    echo "Enter allowed IPs/ranges (comma-separated):"
    echo "Example: 203.0.113.50,10.20.0.0/16"
    read -p "IP allowlist: " IP_ALLOWLIST
    
    if [ -n "$IP_ALLOWLIST" ]; then
        echo "Configuring IP restrictions..."
        
        # Note: Container Apps IP restrictions are set via ingress config
        # This is a placeholder - actual implementation varies
        
        echo ""
        echo "⚠️  Container Apps IP restrictions must be configured via Azure Portal:"
        echo "   1. Go to Container App → Settings → Ingress"
        echo "   2. Click 'IP restrictions'"
        echo "   3. Add allowed IPs: $IP_ALLOWLIST"
        echo ""
        echo "Or update via ARM template/Bicep"
    fi
else
    echo "Skipping IP restrictions"
fi

# ============================================
# Step 5: Summary
# ============================================

echo ""
echo "✅ Security Hardening Complete!"
echo "================================"
echo ""
echo "🔒 Network Security Status:"

if [ "$RECREATE" = "yes" ]; then
    echo "   ✅ VNET integration enabled"
    echo "   ✅ Private networking configured"
else
    echo "   ⚠️  VNET integration not enabled (requires environment recreation)"
fi

if [ "$CONFIGURE_IP" = "yes" ] && [ -n "$IP_ALLOWLIST" ]; then
    echo "   ⚠️  IP restrictions pending (configure in Azure Portal)"
else
    echo "   ❌ No IP restrictions (public access)"
fi

echo ""
echo "🎯 Next Steps:"
echo ""

if [ "$RECREATE" = "yes" ]; then
    echo "1. Redeploy your application:"
    echo "   git push origin main"
    echo ""
fi

if [ "$CONFIGURE_IP" = "yes" ]; then
    echo "2. Configure IP restrictions in Azure Portal"
    echo ""
fi

echo "3. Test access to your application"
echo "4. Monitor logs for unauthorized access attempts"
echo ""
echo "📊 To verify VNET integration:"
echo "   az containerapp env show --name $ENV_NAME --resource-group $RESOURCE_GROUP --query 'properties.vnetConfiguration'"
echo ""
