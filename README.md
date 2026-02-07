# AI Threat Modeling - Security Enhanced

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

## Setup

### 1. GitHub Secrets

Add to repository secrets:

```
ACR_USERNAME=threatmodelingacr
ACR_PASSWORD=[from Azure]
AZURE_CREDENTIALS=[service principal JSON]
```

### 2. Enable GitHub Advanced Security

1. Repository → Settings → Code security and analysis
2. Enable "CodeQL analysis"
3. Enable "Dependabot alerts"
4. Enable "Dependabot security updates"

### 3. Deploy

**Test build** (any branch):
```bash
git push origin develop
# Builds insecure version for testing
```

**Production** (main branch):
```bash
git push origin main
# Builds secure version with OAuth
# Auto-deploys to Azure
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
APP_URL=https://your-domain.com
```

## Workflow

1. **Push to develop** → Insecure build for testing
2. **Push to main** → Secure build → Auto-deploy to production
3. **Weekly** → Security scans run automatically
4. **Dependabot** → Creates PRs for updates

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
