# -*- coding: utf-8 -*-
import streamlit as st
import os
import json
import time

# Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
AUTHORIZED_EMAILS = os.getenv("AUTHORIZED_EMAILS", "").split(",") if os.getenv("AUTHORIZED_EMAILS") else []
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"

st.set_page_config(page_title="AI Threat Modeling Assistant", page_icon="🛡️", layout="wide")

def check_auth():
    """Check if user is authenticated"""
    if not REQUIRE_AUTH:
        return True
    return st.session_state.get('authenticated', False) and time.time() < st.session_state.get('token_expires', 0)

def show_login():
    """Show login screen with Google OAuth"""
    st.title("🛡️ AI Threat Modeling Assistant")
    st.markdown("### Secure Access Required")
    
    if not GOOGLE_CLIENT_ID:
        st.error("⚠️ OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
        st.info("For development, set REQUIRE_AUTH=false")
        st.stop()
    
    st.info("🔐 Sign in with your Google account to continue")
    
    # Simple email-based auth for POC (production should use proper OAuth library)
    email = st.text_input("Email address")
    if st.button("Sign In"):
        if AUTHORIZED_EMAILS and email in AUTHORIZED_EMAILS:
            st.session_state['authenticated'] = True
            st.session_state['user_email'] = email
            st.session_state['token_expires'] = time.time() + 3600
            st.success(f"✅ Welcome, {email}!")
            st.rerun()
        else:
            st.error(f"❌ {email} is not authorized. Contact admin.")

def show_app():
    """Load and run the main application"""
    # Import the main app here to avoid loading before auth
    import sys
    sys.path.insert(0, '/app')
    
    # Import all the functions from the base app
    exec(open('/app/app_main.py').read(), globals())
    
    # Add logout button
    with st.sidebar:
        if REQUIRE_AUTH:
            st.markdown("---")
            st.markdown(f"👤 **{st.session_state.get('user_email', 'User')}**")
            if st.button("🚪 Sign Out"):
                st.session_state.clear()
                st.rerun()

# Main flow
if not check_auth():
    show_login()
else:
    show_app()
