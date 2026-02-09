# API Integration Guide

Enable programmatic threat model generation from any tool or platform.

## Quick Start

### 1. Enable API Mode

```bash
# Update Container App to run API alongside UI
az containerapp update \
  --name threat-modeling \
  --resource-group threat-modeling-poc \
  --set-env-vars \
    API_ENABLED=true \
    API_PORT=8001 \
    API_KEYS="key1,key2,key3"  # Generate secure keys
```

### 2. Get API Token

```bash
curl -X POST https://your-app-url.azurecontainerapps.io/api/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-api-key"}'

# Response:
# {
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "token_type": "bearer",
#   "expires_in": 86400
# }
```

### 3. Generate Threat Model

```bash
curl -X POST https://your-app-url.azurecontainerapps.io/api/v1/threat-model \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "architecture_description": "Web app with React, Node.js API, PostgreSQL",
    "framework": "STRIDE",
    "model": "gpt-4o"
  }'
```

---

## Client Examples

### Python

```python
import requests

# Configuration
API_URL = "https://your-app-url.azurecontainerapps.io"
API_KEY = "your-api-key"

# Get token
token_response = requests.post(
    f"{API_URL}/api/token",
    json={"api_key": API_KEY}
)
token = token_response.json()["access_token"]

# Generate threat model
response = requests.post(
    f"{API_URL}/api/v1/threat-model",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "architecture_description": "A web app with React frontend and Node.js backend",
        "framework": "STRIDE",
        "model": "gpt-4o"
    }
)

threat_model = response.json()["threat_model"]
print(threat_model)
```

### PowerShell

```powershell
# Configuration
$ApiUrl = "https://your-app-url.azurecontainerapps.io"
$ApiKey = "your-api-key"

# Get token
$tokenResponse = Invoke-RestMethod -Uri "$ApiUrl/api/token" -Method Post -Body (@{
    api_key = $ApiKey
} | ConvertTo-Json) -ContentType "application/json"

$token = $tokenResponse.access_token

# Generate threat model
$response = Invoke-RestMethod -Uri "$ApiUrl/api/v1/threat-model" -Method Post `
    -Headers @{Authorization = "Bearer $token"} `
    -Body (@{
        architecture_description = "Web app with Azure services"
        framework = "STRIDE"
        model = "gpt-4o"
    } | ConvertTo-Json) `
    -ContentType "application/json"

Write-Output $response.threat_model
```

### Node.js / TypeScript

```typescript
import axios from 'axios';

const API_URL = 'https://your-app-url.azurecontainerapps.io';
const API_KEY = 'your-api-key';

async function generateThreatModel(description: string) {
  // Get token
  const tokenResponse = await axios.post(`${API_URL}/api/token`, {
    api_key: API_KEY
  });
  
  const token = tokenResponse.data.access_token;
  
  // Generate threat model
  const response = await axios.post(
    `${API_URL}/api/v1/threat-model`,
    {
      architecture_description: description,
      framework: 'STRIDE',
      model: 'gpt-4o'
    },
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  );
  
  return response.data.threat_model;
}

// Usage
const threatModel = await generateThreatModel('Web app with microservices');
console.log(threatModel);
```

---

## Platform Integrations

### Microsoft Teams Bot

```python
# teams_bot.py
from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount
import requests

class ThreatModelBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        text = turn_context.activity.text
        
        if text.startswith('/threat-model'):
            # Extract architecture description
            description = text.replace('/threat-model', '').strip()
            
            # Generate threat model via API
            threat_model = self.generate_threat_model(description)
            
            # Send to Teams
            await turn_context.send_activity(
                f"**Threat Model Generated:**\n\n{threat_model}"
            )
    
    def generate_threat_model(self, description):
        # Call threat modeling API
        token = self.get_token()
        response = requests.post(
            f"{API_URL}/api/v1/threat-model",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "architecture_description": description,
                "framework": "STRIDE",
                "model": "gpt-4o"
            }
        )
        return response.json()["threat_model"]
```

### VS Code Extension

```typescript
// extension.ts
import * as vscode from 'vscode';
import axios from 'axios';

export function activate(context: vscode.ExtensionContext) {
    let disposable = vscode.commands.registerCommand(
        'threatmodeling.generate',
        async () => {
            // Get selected text or open input
            const editor = vscode.window.activeTextEditor;
            const description = editor?.document.getText(editor.selection) || 
                await vscode.window.showInputBox({
                    prompt: 'Describe your architecture'
                });
            
            if (!description) return;
            
            // Show progress
            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Generating threat model...",
                cancellable: false
            }, async (progress) => {
                // Call API
                const threatModel = await generateThreatModel(description);
                
                // Create new document with results
                const doc = await vscode.workspace.openTextDocument({
                    content: threatModel,
                    language: 'markdown'
                });
                await vscode.window.showTextDocument(doc);
            });
        }
    );
    
    context.subscriptions.push(disposable);
}

async function generateThreatModel(description: string): Promise<string> {
    const config = vscode.workspace.getConfiguration('threatmodeling');
    const apiUrl = config.get<string>('apiUrl');
    const apiKey = config.get<string>('apiKey');
    
    // Get token
    const tokenRes = await axios.post(`${apiUrl}/api/token`, {
        api_key: apiKey
    });
    
    // Generate
    const res = await axios.post(
        `${apiUrl}/api/v1/threat-model`,
        {
            architecture_description: description,
            framework: 'STRIDE',
            model: 'gpt-4o'
        },
        {
            headers: { Authorization: `Bearer ${tokenRes.data.access_token}` }
        }
    );
    
    return res.data.threat_model;
}
```

### Azure DevOps Pipeline

```yaml
# azure-pipelines.yml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: PowerShell@2
  displayName: 'Generate Threat Model'
  inputs:
    targetType: 'inline'
    script: |
      # Read architecture from file
      $architecture = Get-Content architecture.md -Raw
      
      # Get API token
      $tokenResponse = Invoke-RestMethod -Uri "$(ThreatModelApiUrl)/api/token" `
        -Method Post -Body (@{api_key = "$(ThreatModelApiKey)"} | ConvertTo-Json) `
        -ContentType "application/json"
      
      # Generate threat model
      $response = Invoke-RestMethod -Uri "$(ThreatModelApiUrl)/api/v1/threat-model" `
        -Method Post `
        -Headers @{Authorization = "Bearer $($tokenResponse.access_token)"} `
        -Body (@{
          architecture_description = $architecture
          framework = "STRIDE"
          model = "gpt-4o"
        } | ConvertTo-Json) `
        -ContentType "application/json"
      
      # Save to artifact
      $response.threat_model | Out-File threat-model.md
      
- task: PublishBuildArtifacts@1
  inputs:
    PathtoPublish: 'threat-model.md'
    ArtifactName: 'ThreatModel'
```

### GitHub Actions

```yaml
# .github/workflows/threat-model.yml
name: Generate Threat Model

on:
  pull_request:
    paths:
      - 'architecture/**'

jobs:
  threat-model:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Generate Threat Model
        env:
          API_URL: ${{ secrets.THREAT_MODEL_API_URL }}
          API_KEY: ${{ secrets.THREAT_MODEL_API_KEY }}
        run: |
          # Get architecture description
          ARCH_DESC=$(cat architecture/design.md)
          
          # Get token
          TOKEN=$(curl -s -X POST $API_URL/api/token \
            -H "Content-Type: application/json" \
            -d "{\"api_key\": \"$API_KEY\"}" | jq -r .access_token)
          
          # Generate threat model
          curl -X POST $API_URL/api/v1/threat-model \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "{
              \"architecture_description\": \"$ARCH_DESC\",
              \"framework\": \"STRIDE\",
              \"model\": \"gpt-4o\"
            }" | jq -r .threat_model > threat-model.md
      
      - name: Comment on PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const threatModel = fs.readFileSync('threat-model.md', 'utf8');
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## 🛡️ Threat Model Generated\n\n${threatModel}`
            });
```

### Slack Bot

```python
# slack_bot.py
from slack_bolt import App
import requests
import os

app = App(token=os.environ["SLACK_BOT_TOKEN"])

@app.command("/threat-model")
def threat_model_command(ack, command, say):
    ack()
    
    # Extract architecture from command
    description = command['text']
    
    if not description:
        say("Please provide an architecture description: `/threat-model Your architecture here`")
        return
    
    # Generate threat model
    say("🔄 Generating threat model...")
    
    try:
        # Get token
        token_response = requests.post(
            f"{API_URL}/api/token",
            json={"api_key": API_KEY}
        )
        token = token_response.json()["access_token"]
        
        # Generate
        response = requests.post(
            f"{API_URL}/api/v1/threat-model",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "architecture_description": description,
                "framework": "STRIDE",
                "model": "gpt-4o"
            }
        )
        
        threat_model = response.json()["threat_model"]
        
        # Send to Slack
        say({
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🛡️ Threat Model Generated*\n\n{threat_model[:3000]}"
                    }
                }
            ]
        })
    except Exception as e:
        say(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    app.start(port=3000)
```

---

## API Endpoints

### Authentication

**POST /api/token**
```json
Request:
{
  "api_key": "your-api-key"
}

Response:
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### Generate Threat Model

**POST /api/v1/threat-model**
```json
Request:
{
  "architecture_description": "Your architecture",
  "framework": "STRIDE",
  "model": "gpt-4o"
}

Response:
{
  "threat_model": "# Threat Model...",
  "framework": "STRIDE",
  "model_used": "gpt-4o",
  "timestamp": "2024-02-09T12:00:00",
  "metadata": {...}
}
```

### Compare Models

**POST /api/v1/threat-model/compare**
```json
Request:
{
  "architecture_description": "Your architecture",
  "framework": "STRIDE",
  "model": "gpt-4o",
  "compare_model": "gpt-4"
}

Response:
{
  "primary_model": "gpt-4o",
  "secondary_model": "gpt-4",
  "primary_threat_model": "...",
  "secondary_threat_model": "...",
  "framework": "STRIDE",
  "timestamp": "2024-02-09T12:00:00"
}
```

### Upload Files

**POST /api/v1/threat-model/upload**
```bash
curl -X POST /api/v1/threat-model/upload \
  -H "Authorization: Bearer TOKEN" \
  -F "files=@diagram.png" \
  -F "files=@architecture.pdf" \
  -F "architecture_description=Additional context" \
  -F "framework=STRIDE"
```

---

## Configuration

### Environment Variables

```bash
# Enable API
API_ENABLED=true
API_PORT=8001

# Authentication
API_KEY_ENABLED=true
API_KEYS=key1,key2,key3
JWT_SECRET=your-secret-key
JWT_EXPIRY_HOURS=24

# Rate Limiting
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=60
```

### Generate Secure API Keys

```bash
# Generate random API keys
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Store in Key Vault
az keyvault secret set \
  --vault-name threat-modeling-kv \
  --name api-keys \
  --value "key1,key2,key3"
```

---

## Security

- ✅ JWT-based authentication
- ✅ API key validation
- ✅ Rate limiting (10 req/min per key)
- ✅ Input validation & sanitization
- ✅ Prompt injection protection
- ✅ File malware scanning
- ✅ HTTPS only

---

## Rate Limits

| Plan | Requests/Minute | Concurrent |
|------|-----------------|------------|
| Default | 10 | 2 |
| Custom | Configurable | Configurable |

**Comparison endpoint:** Counts as 2 requests

---

## Cost

API calls use same Azure OpenAI resources:
- Standard request: ~$0.50-$2
- Comparison: ~$1-$4 (2x models)

No additional API hosting cost (runs in same Container App).

---

## Documentation

- **Interactive docs:** https://your-app/api/docs
- **ReDoc:** https://your-app/api/redoc
- **OpenAPI spec:** https://your-app/api/openapi.json

---

## Summary

**Enable API access for:**
- ✅ MS Teams integration
- ✅ VS Code extension
- ✅ CI/CD pipelines
- ✅ Slack/Discord bots
- ✅ Custom tooling
- ✅ Automated workflows

**Deployment: Simple environment variable configuration!** 🚀
