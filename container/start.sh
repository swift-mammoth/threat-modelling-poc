#!/bin/bash
# Startup script for Threat Modeling Application
# Runs Streamlit UI and optionally FastAPI

set -e

echo "🚀 Starting Threat Modeling Application"
echo "========================================"

# Check if API mode is enabled
API_ENABLED=${API_ENABLED:-false}
API_PORT=${API_PORT:-8001}
STREAMLIT_PORT=${STREAMLIT_PORT:-8000}

if [ "$API_ENABLED" = "true" ]; then
    echo "✅ API Mode: ENABLED"
    echo "   API Port: $API_PORT"
    echo "   UI Port: $STREAMLIT_PORT"
    echo ""
    
    # Start FastAPI in background
    echo "Starting FastAPI server..."
    cd /app
    uvicorn api:app --host 0.0.0.0 --port $API_PORT &
    API_PID=$!
    
    echo "✅ API started (PID: $API_PID)"
    echo "   Docs: http://localhost:$API_PORT/api/docs"
    echo ""
    
    # Wait a moment for API to start
    sleep 2
    
    # Start Streamlit
    echo "Starting Streamlit UI..."
    streamlit run app.py --server.port=$STREAMLIT_PORT --server.address=0.0.0.0
else
    echo "❌ API Mode: DISABLED"
    echo "   UI Port: $STREAMLIT_PORT"
    echo ""
    echo "To enable API, set: API_ENABLED=true"
    echo ""
    
    # Start only Streamlit
    echo "Starting Streamlit UI..."
    streamlit run app.py --server.port=$STREAMLIT_PORT --server.address=0.0.0.0
fi
