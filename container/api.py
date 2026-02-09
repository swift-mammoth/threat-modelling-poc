# -*- coding: utf-8 -*-
"""
Threat Modeling API
REST API for programmatic threat model generation
"""

from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import os
import base64
import jwt
from datetime import datetime, timedelta
import secrets

# Import existing modules
from app_main import generate_threat_model as generate_tm
from prompt_protection import detect_prompt_injection, sanitize_input
from file_security import validate_file, get_file_info

# FastAPI app
app = FastAPI(
    title="AI Threat Modeling API",
    description="Generate security threat models programmatically",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# API Configuration
API_KEY_ENABLED = os.getenv("API_KEY_ENABLED", "true").lower() == "true"
API_KEYS = os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else []
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

# Rate limiting (simple in-memory - use Redis for production)
from collections import defaultdict
from time import time

rate_limit_store = defaultdict(list)
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds


# ============================================
# Models
# ============================================

class ThreatModelRequest(BaseModel):
    architecture_description: str = Field(..., max_length=50000, description="Architecture description")
    framework: str = Field(default="STRIDE", description="Threat modeling framework")
    model: Optional[str] = Field(default="gpt-4o", description="AI model to use")
    compare_model: Optional[str] = Field(default=None, description="Second model for comparison")
    
    class Config:
        schema_extra = {
            "example": {
                "architecture_description": "A web application with React frontend, Node.js API, and PostgreSQL database",
                "framework": "STRIDE",
                "model": "gpt-4o"
            }
        }


class ThreatModelResponse(BaseModel):
    threat_model: str
    framework: str
    model_used: str
    timestamp: str
    metadata: dict


class ComparisonResponse(BaseModel):
    primary_model: str
    secondary_model: str
    primary_threat_model: str
    secondary_threat_model: str
    framework: str
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


# ============================================
# Authentication
# ============================================

def verify_api_key(api_key: str) -> bool:
    """Verify API key"""
    if not API_KEY_ENABLED:
        return True
    return api_key in API_KEYS


def create_access_token(api_key: str) -> str:
    """Create JWT access token"""
    payload = {
        "api_key": api_key,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token"""
    if not API_KEY_ENABLED:
        return {"api_key": "disabled"}
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        
        # Verify API key is still valid
        if not verify_api_key(payload.get("api_key")):
            raise HTTPException(status_code=401, detail="API key revoked")
        
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ============================================
# Rate Limiting
# ============================================

def check_rate_limit(api_key: str) -> bool:
    """Check if request is within rate limit"""
    now = time()
    
    # Clean old entries
    rate_limit_store[api_key] = [
        timestamp for timestamp in rate_limit_store[api_key]
        if now - timestamp < RATE_LIMIT_WINDOW
    ]
    
    # Check limit
    if len(rate_limit_store[api_key]) >= RATE_LIMIT_REQUESTS:
        return False
    
    # Add current request
    rate_limit_store[api_key].append(now)
    return True


# ============================================
# API Endpoints
# ============================================

@app.get("/", response_model=HealthResponse)
async def root():
    """API root - health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.post("/api/token", response_model=TokenResponse)
async def get_token(request: TokenRequest):
    """
    Get JWT access token
    
    Provide your API key to receive a JWT token for API access.
    """
    if not verify_api_key(request.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    token = create_access_token(request.api_key)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": JWT_EXPIRY_HOURS * 3600
    }


@app.post("/api/v1/threat-model", response_model=ThreatModelResponse)
async def create_threat_model(
    request: ThreatModelRequest,
    token_data: dict = Depends(verify_token)
):
    """
    Generate threat model from architecture description
    
    **Parameters:**
    - architecture_description: Text description of your architecture
    - framework: STRIDE, PASTA, LINDDUN, or VAST
    - model: AI model to use (gpt-4o, gpt-4, gpt-4-turbo, gpt-35-turbo)
    
    **Returns:**
    - Complete threat model in markdown format
    """
    # Rate limiting
    api_key = token_data.get("api_key", "default")
    if not check_rate_limit(api_key):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds"
        )
    
    # Input validation
    if not request.architecture_description.strip():
        raise HTTPException(status_code=400, detail="Architecture description is required")
    
    # Security validation
    is_safe, reason = detect_prompt_injection(request.architecture_description)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Security check failed: {reason}")
    
    # Sanitize input
    clean_description = sanitize_input(request.architecture_description)
    
    # Validate framework
    if request.framework not in ["STRIDE", "PASTA", "LINDDUN", "VAST"]:
        raise HTTPException(status_code=400, detail="Invalid framework. Use: STRIDE, PASTA, LINDDUN, or VAST")
    
    try:
        # Generate threat model
        threat_model = generate_tm(
            clean_description,
            framework=request.framework,
            model_deployment=request.model
        )
        
        if not threat_model:
            raise HTTPException(status_code=500, detail="Failed to generate threat model")
        
        return {
            "threat_model": threat_model,
            "framework": request.framework,
            "model_used": request.model,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "input_length": len(clean_description),
                "output_length": len(threat_model)
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating threat model: {str(e)}")


@app.post("/api/v1/threat-model/compare", response_model=ComparisonResponse)
async def compare_threat_models(
    request: ThreatModelRequest,
    token_data: dict = Depends(verify_token)
):
    """
    Generate threat models from two different AI models for comparison
    
    **Parameters:**
    - architecture_description: Text description of your architecture
    - framework: STRIDE, PASTA, LINDDUN, or VAST
    - model: Primary AI model
    - compare_model: Secondary AI model for comparison
    
    **Returns:**
    - Threat models from both models for side-by-side comparison
    """
    # Rate limiting (counts as 2 requests)
    api_key = token_data.get("api_key", "default")
    if not check_rate_limit(api_key) or not check_rate_limit(api_key):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds"
        )
    
    if not request.compare_model:
        raise HTTPException(status_code=400, detail="compare_model is required for comparison")
    
    if request.model == request.compare_model:
        raise HTTPException(status_code=400, detail="Primary and comparison models must be different")
    
    # Security validation
    is_safe, reason = detect_prompt_injection(request.architecture_description)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Security check failed: {reason}")
    
    clean_description = sanitize_input(request.architecture_description)
    
    try:
        # Generate from primary model
        primary_threat_model = generate_tm(
            clean_description,
            framework=request.framework,
            model_deployment=request.model
        )
        
        # Generate from comparison model
        secondary_threat_model = generate_tm(
            clean_description,
            framework=request.framework,
            model_deployment=request.compare_model
        )
        
        if not primary_threat_model or not secondary_threat_model:
            raise HTTPException(status_code=500, detail="Failed to generate one or both threat models")
        
        return {
            "primary_model": request.model,
            "secondary_model": request.compare_model,
            "primary_threat_model": primary_threat_model,
            "secondary_threat_model": secondary_threat_model,
            "framework": request.framework,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating threat models: {str(e)}")


@app.post("/api/v1/threat-model/upload")
async def create_threat_model_with_files(
    architecture_description: Optional[str] = Form(None),
    framework: str = Form("STRIDE"),
    model: str = Form("gpt-4o"),
    files: List[UploadFile] = File(...),
    token_data: dict = Depends(verify_token)
):
    """
    Generate threat model from uploaded files (diagrams, PDFs)
    
    **Upload:**
    - files: One or more files (PNG, JPG, PDF, TXT, MD)
    - architecture_description: Optional additional text description
    - framework: STRIDE, PASTA, LINDDUN, or VAST
    - model: AI model to use
    
    **Returns:**
    - Complete threat model based on uploaded files and description
    """
    # Rate limiting
    api_key = token_data.get("api_key", "default")
    if not check_rate_limit(api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    if not files and not architecture_description:
        raise HTTPException(status_code=400, detail="Either files or architecture_description is required")
    
    # Process files
    images = []
    text_content = []
    
    for uploaded_file in files:
        file_content = await uploaded_file.read()
        file_ext = uploaded_file.filename.split('.')[-1].lower() if '.' in uploaded_file.filename else ''
        
        # Validate file
        is_safe, reason = validate_file(file_content, uploaded_file.filename, file_ext)
        if not is_safe:
            raise HTTPException(status_code=400, detail=f"File validation failed for {uploaded_file.filename}: {reason}")
        
        # Process based on type
        if uploaded_file.content_type.startswith('image/'):
            # Encode image
            base64_image = base64.b64encode(file_content).decode('utf-8')
            images.append({
                'name': uploaded_file.filename,
                'data': base64_image,
                'type': uploaded_file.content_type
            })
        elif uploaded_file.content_type == 'application/pdf' or file_ext == 'pdf':
            # Extract text from PDF (simplified - would use PyPDF2 in real implementation)
            text = file_content.decode('utf-8', errors='ignore')
            text_content.append(f"=== {uploaded_file.filename} ===\n{text}")
        else:
            # Text file
            text = file_content.decode('utf-8', errors='ignore')
            text_content.append(f"=== {uploaded_file.filename} ===\n{text}")
    
    # Combine text content
    additional_context = "\n\n".join(text_content) if text_content else ""
    
    # Security validation on description
    if architecture_description:
        is_safe, reason = detect_prompt_injection(architecture_description)
        if not is_safe:
            raise HTTPException(status_code=400, detail=f"Security check failed: {reason}")
        architecture_description = sanitize_input(architecture_description)
    
    try:
        # Generate threat model
        threat_model = generate_tm(
            architecture_description or "",
            framework=framework,
            images=images if images else None,
            additional_context=additional_context,
            model_deployment=model
        )
        
        if not threat_model:
            raise HTTPException(status_code=500, detail="Failed to generate threat model")
        
        return {
            "threat_model": threat_model,
            "framework": framework,
            "model_used": model,
            "timestamp": datetime.utcnow().isoformat(),
            "files_processed": len(files)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================
# Run API Server
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("API_PORT", "8001"))
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
