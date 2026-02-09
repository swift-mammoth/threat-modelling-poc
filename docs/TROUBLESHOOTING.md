# Common Workflow Issues - Quick Fixes

## Issue 1: CodeQL "Resource not accessible by integration"

**Error:**
```
Resource not accessible by integration
This run does not have permission to access CodeQL Action API endpoints
```

**Fix:**

Ensure workflow has correct permissions:

```yaml
# Top-level permissions
permissions:
  contents: write
  security-events: write  # ← Required!
  actions: read           # ← Required!
  id-token: write

# Job-level permissions
jobs:
  codeql-analysis:
    permissions:
      contents: read
      security-events: write  # ← Required!
      actions: read           # ← Required!
```

**Updated workflow already has this fix!**

---

## Issue 2: OIDC "No matching federated identity"

**Error:**
```
AADSTS70021: No matching federated identity record found
```

**Fix:**

Check federated credentials match your repo:

```bash
# List existing credentials
az ad app federated-credential list --id $APP_ID

# Should show:
# subject: repo:YOUR-ORG/YOUR-REPO:ref:refs/heads/main
# subject: repo:YOUR-ORG/YOUR-REPO:pull_request
```

**If wrong repo:** Delete and recreate:

```bash
# Delete old credentials
az ad app federated-credential delete --id $APP_ID --federated-credential-id CRED_ID

# Re-run setup script with correct repo
nano setup-github-oidc.sh  # Update GITHUB_ORG and GITHUB_REPO
./setup-github-oidc.sh
```

---

## Issue 3: Key Vault Access Denied

**Error:**
```
The user, group or application does not have secrets get permission
```

**Fix:**

Grant managed identity access to Key Vault:

```bash
# Get Container App identity
PRINCIPAL_ID=$(az containerapp show \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --query identity.principalId -o tsv)

# Grant access
az keyvault set-policy \
  --name threat-modeling-kv \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

---

## Issue 4: ACR Login Failed (OIDC)

**Error:**
```
unauthorized: authentication required
```

**Fix:**

Ensure service principal has AcrPush role:

```bash
# Check role
az role assignment list \
  --assignee $APP_ID \
  --scope $(az acr show --name threatmodelingacr --query id -o tsv)

# If missing, assign:
az role assignment create \
  --assignee $APP_ID \
  --role AcrPush \
  --scope $(az acr show --name threatmodelingacr --query id -o tsv)
```

---

## Issue 5: Container App Can't Pull from ACR

**Error:**
```
Failed to pull image: unauthorized
```

**Fix:**

Grant Container App managed identity AcrPull access:

```bash
# Get Container App identity
PRINCIPAL_ID=$(az containerapp show \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --query identity.principalId -o tsv)

# Grant AcrPull
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role AcrPull \
  --scope $(az acr show --name threatmodelingacr --query id -o tsv)
```

Then configure Container App to use managed identity via Azure Portal:
1. Container App → Containers → Edit
2. Registry → Change to "Managed identity"
3. Save

---

## Issue 6: Secrets Not Syncing from Key Vault

**Error:**
```
Application error / Configuration error
```

**Fix:**

Check secrets are configured correctly:

```bash
# View Container App secrets
az containerapp secret list \
  --name threat-modeling \
  --resource-group threat-modeling-poc

# Should show KeyVaultUrl for each secret
```

**If missing KeyVaultUrl:**

```bash
# Re-link to Key Vault
az containerapp secret set \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --secrets \
    azure-openai-key="keyvaultref:https://threat-modeling-kv.vault.azure.net/secrets/azure-openai-key,identityref:system"

# Update env var to use secret
az containerapp update \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --set-env-vars AZURE_OPENAI_KEY=secretref:azure-openai-key
```

---

## Issue 7: GitHub Actions Can't Post Comments

**Error:**
```
Resource not accessible by integration (post comments)
```

**Fix:**

Workflow needs `contents: write`:

```yaml
permissions:
  contents: write  # ← Required for posting comments
  id-token: write
```

---

## Issue 8: Workflow Doesn't Run

**Check:**

1. **Disabled CodeQL default setup?**
   - Settings → Code security → CodeQL analysis → Disable default setup

2. **Correct branch name?**
   - Workflow triggers on `main` - check your default branch

3. **Workflow file in correct location?**
   - Must be in `.github/workflows/`

---

## Quick Verification Commands

```bash
# Check Container App is running
az containerapp show --name threat-modeling --resource-group threat-modeling-poc --query properties.runningStatus

# Check Key Vault secrets
az keyvault secret list --vault-name threat-modeling-kv --output table

# Check Container App has managed identity
az containerapp show --name threat-modeling --resource-group threat-modeling-poc --query identity

# Check logs
az containerapp logs show --name threat-modeling --resource-group threat-modeling-poc --follow

# Test Key Vault access from Container App
az containerapp exec --name threat-modeling --resource-group threat-modeling-poc --command "/bin/bash"
# Then: curl "http://169.254.169.254/metadata/identity/oauth2/token?resource=https://vault.azure.net"
```

---

## Complete Reset (Nuclear Option)

If everything is broken:

```bash
# 1. Delete everything
az containerapp delete --name threat-modeling --resource-group threat-modeling-poc --yes
az keyvault delete --name threat-modeling-kv --resource-group threat-modeling-poc
az keyvault purge --name threat-modeling-kv

# 2. Re-run clean setup
./clean-setup.sh

# 3. Re-run OIDC setup
./setup-github-oidc.sh

# 4. Update GitHub secrets
# Add: AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID

# 5. Push to trigger workflow
git commit --allow-empty -m "Trigger rebuild"
git push origin main
```

---

## Summary

Most issues are permission-related:

✅ **CodeQL:** Needs `security-events: write` + `actions: read`
✅ **OIDC:** Needs `id-token: write`
✅ **Key Vault:** Needs managed identity with `get list` permissions
✅ **ACR (push):** Service principal needs `AcrPush` role
✅ **ACR (pull):** Container App identity needs `AcrPull` role
✅ **Comments:** Needs `contents: write`

**The updated workflow has all these fixes!** 🚀
