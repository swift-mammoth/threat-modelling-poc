

# Google OAuth Configuration for Secure Container
==============================================

1. Go to: https://console.cloud.google.com
2. Create/Select project
3. APIs & Services → Credentials"
4. Create OAuth 2.0 Client ID"
5. Application type: Web application"
6. Authorized redirect URIs:"
   - https://your-domain.com/component/streamlit_oauth.oauth2_component"
   - http://localhost:8000/component/streamlit_oauth.oauth2_component"

7. Add to Azure Container Instance:"
az container create \
  --environment-variables \
    REQUIRE_AUTH=true \
    GOOGLE_CLIENT_ID=your-client-id \
    APP_URL=https://your-domain.com \
    AUTHORIZED_EMAILS=user1@company.com,user2@company.com \
  --secure-environment-variables \
    GOOGLE_CLIENT_SECRET=your-secret"
echo "For development/testing, disable auth:"
echo "  REQUIRE_AUTH=false"
