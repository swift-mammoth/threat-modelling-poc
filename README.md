# AI Threat Modeling - Security Enhanced

## This project borrows heavily from https://github.com/build-on-aws/threat-model-accelerator-with-genai

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

## Setup

### 1. Deploy to Azure Container Apps

**Initial deployment (manual):**

```bash
# Deploy Container App with OAuth
az containerapp create \
  --name threat-modeling \
  --resource-group rg-threat-modeling-poc \
  --environment threat-modeling-env \
  --image threatmodelingacr.azurecr.io/threat-modeling:latest \
  --registry-server threatmodelingacr.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --cpu 1.0 --memory 2.0Gi \
  --set-env-vars \
    AZURE_OPENAI_ENDPOINT="https://..." \
    AZURE_OPENAI_DEPLOYMENT="gpt-4o" \
    REQUIRE_AUTH="true" \
    AUTHORIZED_EMAILS="user@company.com" \
  --replace-env-vars \
    AZURE_OPENAI_KEY="your-key" \
    GOOGLE_CLIENT_SECRET="your-secret"
```

### 2. GitHub Secrets

Add to repository secrets:

```
ACR_USERNAME=threatmodelingacr
ACR_PASSWORD=[from Azure]
AZURE_CREDENTIALS=[service principal JSON]
```

### 3. Enable GitHub Advanced Security

1. Repository → Settings → Code security and analysis
2. Enable "CodeQL analysis"
3. Enable "Dependabot alerts"
4. Enable "Dependabot security updates"

### 4. Deploy

**Test build** (any branch):
```bash
git push origin develop
# Builds insecure version for testing
```

**Production** (main branch):
```bash
git push origin main
# Builds secure version with OAuth
# Auto-deploys to Azure Container Apps
```

## Environment Variables

### Insecure (Development)
```
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview
```

### Secure (Production)
Same as above, plus:
```
REQUIRE_AUTH=true
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
AUTHORIZED_EMAILS=user@company.com,user2@company.com
APP_URL=https://your-containerapp-url.azurecontainerapps.io
```

## Workflow

1. **Push to develop** → Insecure build for testing
2. **Push to main** → Secure build → Auto-deploy to Container Apps
3. **Weekly** → Security scans run automatically
4. **Dependabot** → Creates PRs for updates

## Deployment Target

**Azure Container Apps** (not Container Instances)
- Automatic HTTPS with managed certificate
- Auto-scaling support
- Environment variable updates without recreation
- Cost: ~$20-30/month

**GitHub Actions deploys via:**
```bash
az containerapp update \
  --name threat-modeling \
  --resource-group rg-threat-modeling-poc \
  --image threatmodelingacr.azurecr.io/threat-modeling:latest
```

## Security Scans

- **CodeQL**: Advanced semantic code analysis
- **Dependency Review**: Checks PRs for vulnerable dependencies  
- **Trivy**: Container image vulnerabilities
- **Dependabot**: Weekly dependency updates

Results visible in: Repository → Security tab

## Quick Start

```bash
# Local test (insecure)
cd container
docker build -t threat-modeling:test .
docker run -p 8000:8000 \
  -e AZURE_OPENAI_ENDPOINT=... \
  -e AZURE_OPENAI_KEY=... \
  -e AZURE_OPENAI_DEPLOYMENT=gpt-4o \
  threat-modeling:test

# Push to production
git add .
git commit -m "Update"
git push origin main
```

## License

MIT
