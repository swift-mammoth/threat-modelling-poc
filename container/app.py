# -*- coding: utf-8 -*-
import streamlit as st
import os
import time
from urllib.parse import urlencode
import requests

# Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
AUTHORIZED_EMAILS = os.getenv("AUTHORIZED_EMAILS", "").split(",") if os.getenv("AUTHORIZED_EMAILS") else []
AUTHORIZED_DOMAINS = os.getenv("AUTHORIZED_DOMAINS", "gmail.com").split(",")  # Allow all Gmail by default
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"

def check_auth():
    """Check if user is authenticated"""
    if not REQUIRE_AUTH:
        return True
    return st.session_state.get('authenticated', False) and time.time() < st.session_state.get('token_expires', 0)

def is_authorized(email):
    """Check if email is authorized"""
    # If specific emails are configured, check those first
    if AUTHORIZED_EMAILS and AUTHORIZED_EMAILS[0]:
        return email in AUTHORIZED_EMAILS
    
    # Otherwise check domains (e.g., anyone with @gmail.com)
    if AUTHORIZED_DOMAINS:
        email_domain = email.split('@')[1] if '@' in email else ''
        return email_domain in AUTHORIZED_DOMAINS
    
    # If nothing configured, allow all
    return True

def show_login():
    """Show login screen with real Google OAuth"""
    st.set_page_config(page_title="AI Threat Modeling Assistant", page_icon="🛡️", layout="wide")
    
    st.title("🛡️ AI Threat Modeling Assistant")
    st.markdown("### Secure Access Required")
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        st.error("⚠️ OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
        st.info("💡 For development, set REQUIRE_AUTH=false to bypass authentication")
        st.stop()
    
    # Check for OAuth callback
    query_params = st.query_params
    
    if "code" in query_params:
        # Exchange code for token
        with st.spinner("Authenticating with Google..."):
            try:
                token_url = "https://oauth2.googleapis.com/token"
                redirect_uri = f"{APP_URL}/"
                
                token_data = {
                    "code": query_params["code"],
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                }
                
                token_response = requests.post(token_url, data=token_data)
                token_json = token_response.json()
                
                if "access_token" in token_json:
                    # Get user info
                    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
                    headers = {"Authorization": f"Bearer {token_json['access_token']}"}
                    userinfo_response = requests.get(userinfo_url, headers=headers)
                    userinfo = userinfo_response.json()
                    
                    email = userinfo.get("email", "")
                    name = userinfo.get("name", email)
                    
                    # Check if authorized
                    if is_authorized(email):
                        st.session_state['authenticated'] = True
                        st.session_state['user_email'] = email
                        st.session_state['user_name'] = name
                        st.session_state['token_expires'] = time.time() + 3600
                        
                        # Clear query params and reload
                        st.query_params.clear()
                        st.success(f"✅ Welcome, {name}!")
                        st.rerun()
                    else:
                        st.error(f"❌ Access denied for {email}")
                        if AUTHORIZED_EMAILS and AUTHORIZED_EMAILS[0]:
                            st.info(f"Only these emails are authorized: {', '.join(AUTHORIZED_EMAILS)}")
                        elif AUTHORIZED_DOMAINS:
                            st.info(f"Only emails from these domains are authorized: {', '.join(AUTHORIZED_DOMAINS)}")
                        st.stop()
                else:
                    st.error("❌ Authentication failed. Please try again.")
                    st.stop()
                    
            except Exception as e:
                st.error(f"❌ Authentication error: {str(e)}")
                st.stop()
    
    # Show login button
    st.info("🔐 Sign in with your Google account to continue")
    
    # Google OAuth URL
    redirect_uri = f"{APP_URL}/"
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account"
    }
    
    google_login_url = f"{auth_url}?{urlencode(params)}"
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <a href="{google_login_url}" target="_self">
            <button style="
                background-color: #4285f4;
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 16px;
                font-weight: 500;
                border-radius: 4px;
                cursor: pointer;
                width: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
                text-decoration: none;
            ">
                <img src="https://www.google.com/favicon.ico" width="20" style="margin-right: 10px;">
                Sign in with Google
            </button>
        </a>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    if AUTHORIZED_DOMAINS:
        st.caption(f"✅ Authorized domains: {', '.join(AUTHORIZED_DOMAINS)}")
    if AUTHORIZED_EMAILS and AUTHORIZED_EMAILS[0]:
        st.caption(f"✅ Authorized emails: {', '.join(AUTHORIZED_EMAILS)}")

def show_app():
    """Load and run the main application"""
    import sys
    sys.path.insert(0, '/app')
    
    # Import all the functions from the base app
    exec(open('/app/app_main.py').read(), globals())
    
    # Add logout button to sidebar
    with st.sidebar:
        if REQUIRE_AUTH:
            st.markdown("---")
            st.markdown(f"👤 **{st.session_state.get('user_name', 'User')}**")
            st.caption(st.session_state.get('user_email', ''))
            if st.button("🚪 Sign Out"):
                st.session_state.clear()
                st.rerun()

# Main flow
if not check_auth():
    show_login()
else:
    show_app()


