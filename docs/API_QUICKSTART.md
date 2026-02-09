# API Quick Start

Enable API access in 5 minutes.

## Step 1: Generate API Keys

```bash
# Generate 3 secure API keys
python3 -c "import secrets; [print(secrets.token_urlsafe(32)) for _ in range(3)]"

# Example output:
# KEY1: k8jFn2Qp9Xw7Rt5Hv3Bm1Cz6Lp4Dy0Wq2As8
# KEY2: Mx9Lp2Nq5Rt8Hv1Bz4Cw7Ks3Fp6Dy0Xq1Gt5
# KEY3: Qw7Rt3Hp9Bv2Cz5Lx8Ks1Fp4Dy6Mq0As2Gt9
```

## Step 2: Store in Key Vault

```bash
# Store API keys in Key Vault (comma-separated)
az keyvault secret set \
  --vault-name threat-modeling-kv \
  --name api-keys \
  --value "KEY1,KEY2,KEY3"

# Generate JWT secret
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

az keyvault secret set \
  --vault-name threat-modeling-kv \
  --name jwt-secret \
  --value "$JWT_SECRET"
```

## Step 3: Update Container App

```bash
# Link secrets from Key Vault
az containerapp secret set \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --secrets \
    api-keys="keyvaultref:https://threat-modeling-kv.vault.azure.net/secrets/api-keys,identityref:system" \
    jwt-secret="keyvaultref:https://threat-modeling-kv.vault.azure.net/secrets/jwt-secret,identityref:system"

# Enable API mode
az containerapp update \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --set-env-vars \
    API_ENABLED=true \
    API_PORT=8001 \
    API_KEYS=secretref:api-keys \
    JWT_SECRET=secretref:jwt-secret \
    JWT_EXPIRY_HOURS=24 \
    RATE_LIMIT_REQUESTS=10 \
    RATE_LIMIT_WINDOW=60
```

## Step 4: Test API

```bash
# Get your app URL
APP_URL=$(az containerapp show \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --query properties.configuration.ingress.fqdn -o tsv)

# Test health
curl https://$APP_URL/api/health

# Get token
TOKEN=$(curl -s -X POST https://$APP_URL/api/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "KEY1"}' | jq -r .access_token)

# Generate threat model
curl -X POST https://$APP_URL/api/v1/threat-model \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "architecture_description": "Web app with React and Node.js",
    "framework": "STRIDE",
    "model": "gpt-4o"
  }' | jq -r .threat_model
```

## Step 5: Access Documentation

Visit:
- **Swagger UI:** `https://your-app-url/api/docs`
- **ReDoc:** `https://your-app-url/api/redoc`

## Done! 🎉

Your API is now live:
- ✅ Authenticated with API keys
- ✅ JWT tokens for requests
- ✅ Rate limited (10 req/min)
- ✅ Fully documented

## Next Steps

### Distribute API Keys

Share with your team:
```
API Endpoint: https://your-app-url
API Key: KEY1 (for John's team)
API Key: KEY2 (for Sarah's automation)
API Key: KEY3 (for CI/CD pipeline)

Documentation: https://your-app-url/api/docs
```

### Integrate with Tools

See `API_INTEGRATION.md` for examples:
- MS Teams bot
- VS Code extension
- GitHub Actions
- Azure DevOps
- Slack bot
- PowerShell scripts

### Monitor Usage

```bash
# View API logs
az containerapp logs show \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --follow | grep API

# Look for:
# - Authentication attempts
# - Rate limit hits
# - Error rates
```

---

## Configuration Reference

### Environment Variables

```bash
# API Control
API_ENABLED=true              # Enable API mode
API_PORT=8001                 # API port (UI on 8000)

# Authentication
API_KEYS=secretref:api-keys   # Comma-separated keys
JWT_SECRET=secretref:jwt-secret
JWT_EXPIRY_HOURS=24           # Token lifetime

# Rate Limiting
RATE_LIMIT_REQUESTS=10        # Max requests
RATE_LIMIT_WINDOW=60          # Per N seconds
```

### Update API Keys

```bash
# Rotate keys
NEW_KEYS="KEY4,KEY5,KEY6"

az keyvault secret set \
  --vault-name threat-modeling-kv \
  --name api-keys \
  --value "$NEW_KEYS"

# Takes effect in ~30 seconds
```

### Increase Rate Limits

```bash
az containerapp update \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --set-env-vars \
    RATE_LIMIT_REQUESTS=50 \
    RATE_LIMIT_WINDOW=60

# Now: 50 requests per minute
```

---

## Security Notes

- ✅ API keys stored in Key Vault (not GitHub)
- ✅ JWT tokens expire after 24 hours
- ✅ Rate limiting prevents abuse
- ✅ All security validations apply (prompt injection, file scanning)
- ✅ HTTPS only
- ✅ Same authentication as UI (if enabled)

---

## Troubleshooting

### API Not Responding

```bash
# Check if API is enabled
az containerapp show \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --query "properties.template.containers[0].env[?name=='API_ENABLED'].value"

# Check logs
az containerapp logs show \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --follow
```

### Invalid API Key

```bash
# Verify key in Key Vault
az keyvault secret show \
  --vault-name threat-modeling-kv \
  --name api-keys \
  --query value -o tsv

# Should show: KEY1,KEY2,KEY3
```

### Token Expired

```bash
# Get new token (tokens last 24 hours)
curl -X POST https://$APP_URL/api/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "KEY1"}'
```

---

## Cost Impact

**API mode:** $0 additional cost
- Runs in same Container App
- Same OpenAI usage costs
- No separate infrastructure

**Usage costs:**
- API request: ~$0.50-$2 (same as UI)
- Comparison: ~$1-$4 (2x models)

---

## Summary

**Time to deploy:** ~5 minutes
**Additional cost:** $0
**Integration options:** Unlimited

**Your threat modeling tool is now API-enabled!** 🚀
