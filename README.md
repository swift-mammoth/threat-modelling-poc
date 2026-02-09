# AI Threat Modeling Assistant

Generate AI-powered security threat models using Azure OpenAI GPT-4o. Upload architecture diagrams or describe your system to get detailed threat analysis following STRIDE, PASTA, LINDDUN, and VAST frameworks with Australian compliance (AESCSF v2, Essential Eight).

### This project borrows heavily from https://github.com/build-on-aws/threat-model-accelerator-with-genai

## Structure

```
├── container/              # Insecure version (dev/test)
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── container-secure/       # Secure version (production)
│   ├── app.py             # OAuth wrapper
│   ├── app_main.py        # Main app logic
│   ├── Dockerfile
│   └── requirements.txt
└── .github/
    ├── workflows/
    │   └── security-deploy.yml  # GitHub Advanced Security + Deploy
    └── dependabot.yml           # Automated updates
```

## Features

- **GitHub Advanced Security**: CodeQL analysis, Dependency Review
- **Trivy**: Container vulnerability scanning
- **Dependabot**: Automated dependency updates
- **OAuth**: Google authentication (production only)
- **Dual builds**: Insecure (test) + Secure (prod)
- **Azure Container Apps**: HTTPS enabled, auto-scaling

## Prerequisites

### Azure Resources (create these first)

1. **Azure Subscription** with access to:
   - Azure OpenAI Service (GPT-4o model)
   - Resource group creation rights

2. **Create Azure OpenAI Service:**
   ```bash
   # Create resource group
   az group create --name threat-modeling-poc --location australiaeast
   
   # Create Azure OpenAI
   az cognitiveservices account create \
     --name threat-modeling-openai \
     --resource-group threat-modeling-poc \
     --kind OpenAI \
     --sku S0 \
     --location australiaeast
   
   # Deploy GPT-4o model
   az cognitiveservices account deployment create \
     --name threat-modeling-openai \
     --resource-group threat-modeling-poc \
     --deployment-name gpt-4o \
     --model-name gpt-4o \
     --model-version "2024-05-13" \
     --model-format OpenAI \
     --sku-capacity 10 \
     --sku-name "Standard"
   
   # Get endpoint and key
   az cognitiveservices account show \
     --name threat-modeling-openai \
     --resource-group threat-modeling-poc \
     --query properties.endpoint -o tsv
   
   az cognitiveservices account keys list \
     --name threat-modeling-openai \
     --resource-group threat-modeling-poc \
     --query key1 -o tsv
   ```

3. **Create Azure Container Registry:**
   ```bash
   az acr create \
     --name threatmodelingacr \
     --resource-group threat-modeling-poc \
     --sku Basic \
     --location australiaeast
   ```

4. **Create Container Apps Environment:**
   ```bash
   az containerapp env create \
     --name threat-modeling-env \
     --resource-group threat-modeling-poc \
     --location australiaeast
   ```

### Google OAuth (for authentication)

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create new project (or use existing)
3. Create **OAuth 2.0 Client ID** (Web application)
4. Leave redirect URIs empty for now (will add after deployment)
5. Save **Client ID** and **Client Secret**

### GitHub Repository

1. Fork or clone this repository
2. Enable GitHub Advanced Security (Settings → Code security)

---

## Quick Setup (15 minutes)

### 1. Clone Repository
```bash
git clone https://github.com/swift-mammoth/threat-modelling-poc.git
cd threat-modelling-poc
```

### 2. Deploy Infrastructure
```bash
# Edit clean-setup.sh with your values
nano clean-setup.sh

# Update these lines:
OPENAI_KEY="your-key-from-above"
OPENAI_ENDPOINT="https://threat-modeling-openai.openai.azure.com/"
GOOGLE_CLIENT_ID="your-google-client-id"
GOOGLE_CLIENT_SECRET="your-google-client-secret"
AUTHORIZED_DOMAINS="gmail.com"  # Or your company domain

# Run setup
chmod +x clean-setup.sh
./clean-setup.sh
```

**This creates:**
- Azure Key Vault with all secrets
- Container App with managed identity
- HTTPS enabled automatically

**Copy the app URL from the output** - you'll need it next.

### 3. Update Google OAuth
1. Go back to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Click your OAuth client
3. Add **Authorized redirect URIs:**
   ```
   https://your-app-url.azurecontainerapps.io/
   ```
4. Save

### 4. Setup GitHub OIDC (Passwordless CI/CD)
```bash
# Edit setup-github-oidc.sh
nano setup-github-oidc.sh

# Update these lines:
GITHUB_ORG="swift-mammoth"
GITHUB_REPO="threat-modelling-poc"

# Run setup
chmod +x setup-github-oidc.sh
./setup-github-oidc.sh
```

**Add these 3 values to GitHub Secrets** (Settings → Secrets → Actions):
- `AZURE_CLIENT_ID` (from script output)
- `AZURE_TENANT_ID` (from script output)
- `AZURE_SUBSCRIPTION_ID` (from script output)

### 5. Enable Automated Deployments
```bash
# Use the OIDC workflow
cp .github/workflows/security-deploy-oidc.yml .github/workflows/security-deploy.yml

# Commit and push
git add .github/workflows/security-deploy.yml
git commit -m "Enable automated deployments"
git push origin main
```

**Done!** 🎉 Your app is live at the URL from step 2.

---

## Usage

### Accessing the App
Open your app URL and sign in with Google (must be from authorized domain).

### Generating Threat Models
1. **Upload** architecture diagram (PNG/JPG) or PDF, OR
2. **Describe** your system in the text box
3. **Select** framework (STRIDE, PASTA, etc.)
4. **Click** Generate

### Managing Users
```bash
# Allow all Gmail users
az keyvault secret set \
  --vault-name threat-modeling-kv \
  --name authorized-domains \
  --value "gmail.com"

# Or allow your company domain
az keyvault secret set \
  --vault-name threat-modeling-kv \
  --name authorized-domains \
  --value "yourcompany.com"

# Or specific emails
az keyvault secret set \
  --vault-name threat-modeling-kv \
  --name authorized-emails \
  --value "user1@example.com,user2@example.com"
```

Changes take effect in ~30 seconds.

---

## Development

### Local Development
```bash
# Set environment variables
export AZURE_OPENAI_ENDPOINT="https://..."
export AZURE_OPENAI_KEY="..."
export REQUIRE_AUTH="false"

# Run
cd container-secure
streamlit run app.py
```

### Deploying Changes
```bash
# Just push to main
git add .
git commit -m "Your changes"
git push origin main

# GitHub Actions automatically:
# - Scans code
# - Builds container
# - Deploys to Azure
# - Updates version in UI
```

---

## Troubleshooting

**Can't login?**
- Check `AUTHORIZED_DOMAINS` in Key Vault matches your email domain

**OAuth error?**
- Verify redirect URI in Google Console: `https://your-exact-url.azurecontainerapps.io/`

**Container won't start?**
```bash
az containerapp logs show \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --follow
```

**Need to reset everything?**
```bash
# Delete and re-run clean-setup.sh
az containerapp delete --name threat-modeling --resource-group threat-modeling-poc --yes
az keyvault delete --name threat-modeling-kv --resource-group threat-modeling-poc
az keyvault purge --name threat-modeling-kv
./clean-setup.sh
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more solutions.

---

## Cost

Approximately **$40-90/month**:
- Azure Container Apps: $20-30
- Azure OpenAI: $10-50 (usage-based)
- Azure Key Vault: $1-5
- Azure Container Registry: $5

---

## Security Features

- ✅ Google OAuth authentication
- ✅ Azure Key Vault (all secrets)
- ✅ Managed Identity (no passwords in code)
- ✅ GitHub OIDC (no passwords in GitHub)
- ✅ Automated security scanning (CodeQL, Trivy)
- ✅ HTTPS with automatic certificates

---

## Security Scans

- **CodeQL**: Advanced semantic code analysis
- **Dependency Review**: Checks PRs for vulnerable dependencies  
- **Trivy**: Container image vulnerabilities
- **Dependabot**: Weekly dependency updates

Results visible in: Repository → Security tab

---

## License

MIT
