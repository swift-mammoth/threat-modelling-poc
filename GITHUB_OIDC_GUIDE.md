# Passwordless GitHub Actions with OIDC

## Overview

Eliminate **ALL passwords** from GitHub using OpenID Connect (OIDC).

**Zero secrets:**
- ❌ No ACR_PASSWORD
- ❌ No ACR_USERNAME  
- ❌ No AZURE_CREDENTIALS (service principal JSON)
- ✅ Just 3 non-sensitive IDs

---

## Current vs OIDC

### Current (Passwords in GitHub):

```
GitHub Secrets:
├── AZURE_CREDENTIALS     ← JSON with client secret
├── ACR_USERNAME         ← ACR admin username
└── ACR_PASSWORD         ← ACR admin password

Total: 3 sensitive secrets
```

### With OIDC (No Passwords!):

```
GitHub Secrets:
├── AZURE_CLIENT_ID       ← Not sensitive (just an ID)
├── AZURE_TENANT_ID       ← Not sensitive (just an ID)
└── AZURE_SUBSCRIPTION_ID ← Not sensitive (just an ID)

Total: 0 passwords! ✨
```

---

## How It Works

```
┌────────────────────────┐
│ GitHub Actions         │
│                        │
│ 1. Request token ──────┼─→ GitHub OIDC Provider
│                        │       ↓
│ 2. Receive JWT token ←─┼───────┘
│                        │
│ 3. Exchange for Azure  │
│    access token ───────┼─→ Azure AD
│                        │       ↓
│ 4. Authenticated! ←────┼───────┘
└────────────────────────┘
         ↓
    Access Azure
    (ACR, Container Apps)
```

**No passwords stored anywhere!**

---

## Setup

### Step 1: Run Setup Script

```bash
chmod +x setup-github-oidc.sh

# Edit the script first - update your GitHub org/repo
nano setup-github-oidc.sh

# Look for these lines:
GITHUB_ORG="swift-mammoth"
GITHUB_REPO="threat-modelling-poc"

# Run it
./setup-github-oidc.sh
```

The script will:
1. Create Azure AD application
2. Create service principal
3. Grant permissions (Contributor, AcrPush)
4. Configure federated credentials for GitHub
5. Output the 3 IDs you need

### Step 2: Add GitHub Secrets

Go to: https://github.com/your-org/your-repo/settings/secrets/actions

Add these 3 secrets (from script output):

| Secret Name | Value | Sensitive? |
|-------------|-------|------------|
| `AZURE_CLIENT_ID` | `abc-123-def-456` | ❌ No (just an ID) |
| `AZURE_TENANT_ID` | `xyz-789-ghi-012` | ❌ No (just an ID) |
| `AZURE_SUBSCRIPTION_ID` | `sub-456-jkl-789` | ❌ No (just an ID) |

**Note:** These are IDs, not passwords. They're not sensitive on their own.

### Step 3: Update Workflow

```bash
# Use the OIDC workflow
cp .github/workflows/security-deploy-oidc.yml .github/workflows/security-deploy.yml

# Commit
git add .github/workflows/security-deploy.yml
git commit -m "Switch to passwordless OIDC authentication"
git push origin main
```

### Step 4: Remove Old Secrets

```bash
# These are no longer needed!
gh secret remove AZURE_CREDENTIALS
gh secret remove ACR_USERNAME
gh secret remove ACR_PASSWORD
```

---

## Workflow Changes

### Old (With Passwords):

```yaml
steps:
  - name: Azure Login
    uses: azure/login@v1
    with:
      creds: ${{ secrets.AZURE_CREDENTIALS }}  # Contains password!
  
  - name: Login to ACR
    uses: docker/login-action@v3
    with:
      registry: threatmodelingacr.azurecr.io
      username: ${{ secrets.ACR_USERNAME }}    # Password!
      password: ${{ secrets.ACR_PASSWORD }}    # Password!
```

### New (OIDC - No Passwords!):

```yaml
permissions:
  id-token: write  # Required for OIDC

steps:
  - name: Azure Login (OIDC)
    uses: azure/login@v1
    with:
      client-id: ${{ secrets.AZURE_CLIENT_ID }}
      tenant-id: ${{ secrets.AZURE_TENANT_ID }}
      subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
  
  - name: Login to ACR
    run: |
      az acr login --name threatmodelingacr  # Uses Azure identity!
```

**No passwords anywhere!**

---

## Benefits

| Feature | Passwords | OIDC |
|---------|-----------|------|
| **Secrets in GitHub** | 3 passwords | 0 passwords |
| **Rotation needed** | Yes (manual) | No (automatic) |
| **Expiration** | Yes (must renew) | No |
| **If leaked** | Full access | No access (IDs useless without GitHub) |
| **Compliance** | Basic | ✅ Enterprise-grade |
| **Audit trail** | Limited | ✅ Full Azure AD audit |

---

## Security

### With Passwords (Current):

**If someone steals `AZURE_CREDENTIALS`:**
- ✅ They have full access to your Azure
- ✅ Can deploy anywhere
- ✅ Can modify resources
- ❌ Hard to detect
- ❌ Must rotate manually

### With OIDC:

**If someone steals the 3 IDs:**
- ❌ They have NO access
- ❌ IDs only work from your GitHub repo
- ❌ Can't use them anywhere else
- ✅ Easy to detect (Azure AD logs)
- ✅ Just revoke federated credential

**OIDC is significantly more secure!**

---

## Complete Architecture

### Current (3 Passwords):

```
GitHub Secrets:
├── AZURE_CREDENTIALS (password) → Azure
├── ACR_USERNAME (password)      → ACR
└── ACR_PASSWORD (password)      → ACR

App Secrets:
└── All in Key Vault ✅

Total Passwords: 3 in GitHub + 0 in app
```

### With OIDC (0 Passwords):

```
GitHub Secrets:
├── AZURE_CLIENT_ID (ID only)       → Used with OIDC
├── AZURE_TENANT_ID (ID only)       → Used with OIDC
└── AZURE_SUBSCRIPTION_ID (ID only) → Used with OIDC

App Secrets:
└── All in Key Vault ✅

Total Passwords: 0 anywhere! ✨
```

---

## Migration Steps

### 1. Setup OIDC

```bash
./setup-github-oidc.sh
```

### 2. Add GitHub Secrets

```
AZURE_CLIENT_ID
AZURE_TENANT_ID
AZURE_SUBSCRIPTION_ID
```

### 3. Update Workflow

```bash
cp .github/workflows/security-deploy-oidc.yml .github/workflows/security-deploy.yml
git commit -m "Switch to OIDC"
git push
```

### 4. Test

```bash
# Make a change
echo "# Test" >> README.md
git add README.md
git commit -m "Test OIDC workflow"
git push origin main

# Watch Actions tab - should work!
```

### 5. Remove Old Secrets

```bash
gh secret remove AZURE_CREDENTIALS
gh secret remove ACR_USERNAME
gh secret remove ACR_PASSWORD
```

---

## Troubleshooting

### Error: "AADSTS70021: No matching federated identity record found"

**Cause:** Federated credential not configured correctly

**Fix:**
```bash
# Check federated credentials
az ad app federated-credential list --id $APP_ID

# Should show credentials for:
# - repo:ORG/REPO:ref:refs/heads/main
# - repo:ORG/REPO:pull_request
```

### Error: "Insufficient privileges to complete the operation"

**Cause:** Service principal doesn't have required permissions

**Fix:**
```bash
# Re-grant permissions
az role assignment create --assignee $APP_ID --role Contributor --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP
az role assignment create --assignee $APP_ID --role AcrPush --scope $(az acr show --name threatmodelingacr --query id -o tsv)
```

### Workflow doesn't authenticate

**Check:** Make sure workflow has `id-token: write` permission

```yaml
permissions:
  contents: write
  id-token: write  # ← Required!
```

---

## Comparison

### GitHub Secrets Summary

| Approach | Secrets Needed | Passwords | Security |
|----------|----------------|-----------|----------|
| **Current** | 3 | 3 | ⚠️ Medium |
| **Key Vault** | 3 | 3 | ✅ Good |
| **OIDC** | 3 | 0 | ✅✅ Excellent |

### What's Stored Where

| Secret | GitHub (Old) | GitHub (OIDC) | Key Vault |
|--------|--------------|---------------|-----------|
| Azure auth | Password | IDs only | - |
| ACR auth | Password | - (uses Azure) | - |
| OpenAI key | - | - | ✅ Yes |
| Google OAuth | - | - | ✅ Yes |

---

## Best Practice Architecture

```
GitHub Actions (OIDC):
├── AZURE_CLIENT_ID        (ID only)
├── AZURE_TENANT_ID        (ID only)
└── AZURE_SUBSCRIPTION_ID  (ID only)
         ↓
    Authenticates via OIDC (no password!)
         ↓
Azure Services:
├── Container Apps
│   └── Pulls secrets from Key Vault
│
├── ACR
│   └── Push/pull via Azure identity
│
└── Key Vault
    ├── azure-openai-key
    ├── google-client-secret
    └── authorized-domains
```

**Total passwords stored: 0** ✨

---

## Summary

**OIDC Benefits:**
1. ✅ **Zero passwords** in GitHub
2. ✅ **No rotation** needed
3. ✅ **Can't be stolen** (IDs useless outside GitHub)
4. ✅ **Better audit** (Azure AD logs everything)
5. ✅ **Enterprise-grade** security
6. ✅ **Microsoft recommended** approach

**Setup:**
```bash
./setup-github-oidc.sh
# Add 3 IDs to GitHub
# Update workflow
# Done!
```

**This is the most secure way to connect GitHub Actions to Azure!** 🚀
