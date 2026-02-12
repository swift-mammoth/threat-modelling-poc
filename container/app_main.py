# -*- coding: utf-8 -*-
import streamlit as st
import os
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from openai import AzureOpenAI
from azure.storage.blob import BlobServiceClient
from azure.core.credentials import AzureKeyCredential
import json
from datetime import datetime
import traceback
import sys
import base64
from io import BytesIO
from PIL import Image
import PyPDF2

# Import security modules
try:
    from prompt_protection import detect_prompt_injection, sanitize_input, validate_file_content
    from file_security import validate_file, get_file_info
    SECURITY_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Security modules not available: {e}")
    SECURITY_MODULES_AVAILABLE = False

# Import draw.io diagram editor modules
try:
    import streamlit.components.v1 as components
    from threat_model_diagram_editor import DiagramEditor, simple_drawio_embed
    from diagram_threat_integration import integrate_diagram_with_ai, DiagramThreatAnalyzer
    DIAGRAM_EDITOR_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Diagram editor modules not available: {e}")
    DIAGRAM_EDITOR_AVAILABLE = False

# Ensure UTF-8 encoding for stdout/stderr
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# Page configuration
st.set_page_config(
    page_title="AI Threat Modeling Assistant",
    page_icon="🛡️",
    layout="wide"
)

# Initialize Azure credentials
@st.cache_resource
def get_credential():
    """Get Azure credential - works both locally and in App Service"""
    try:
        # Try Managed Identity first (for App Service)
        credential = ManagedIdentityCredential()
        # Test the credential
        credential.get_token("https://management.azure.com/.default")
        return credential
    except Exception as e:
        # Fall back to DefaultAzureCredential (for local development)
        st.info("Using DefaultAzureCredential (local development mode)")
        return DefaultAzureCredential()

# Initialize Azure Storage client
@st.cache_resource
def get_blob_service_client():
    """Initialize blob service client"""
    credential = get_credential()
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    account_url = f"https://{account_name}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=credential)

# Configuration from environment
STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
DIAGRAMS_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER_DIAGRAMS", "architecture-diagrams")
MODELS_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER_MODELS", "threat-models")
ML_WORKSPACE_NAME = os.getenv("AZURE_ML_WORKSPACE_NAME")
RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

def get_ai_client():
    """Get Azure OpenAI client"""
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY:
        return None
    
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
    return client

def encode_image_to_base64(image_file):
    """Encode image to base64 for API"""
    try:
        # Read image file
        image = Image.open(image_file)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large (max 2000px on longest side)
        max_size = 2000
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple([int(dim * ratio) for dim in image.size])
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Save to bytes
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        img_bytes = buffered.getvalue()
        
        # Encode to base64
        return base64.b64encode(img_bytes).decode('utf-8')
    except Exception as e:
        st.error(f"Error encoding image: {str(e)}")
        return None

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n\n"
        return text.strip()
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return None

def process_uploaded_files(uploaded_files):
    """Process uploaded files and extract content"""
    images = []
    text_content = []
    
    for uploaded_file in uploaded_files:
        file_type = uploaded_file.type
        file_name = uploaded_file.name
        file_content = uploaded_file.read()
        
        # Security validation
        if SECURITY_MODULES_AVAILABLE:
            # Get file extension
            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            
            # Validate file
            is_safe, reason = validate_file(file_content, file_name, file_ext)
            if not is_safe:
                st.error(f"🚫 Security check failed for {file_name}: {reason}")
                continue
            
            # Log file info
            file_info = get_file_info(file_content, file_name)
            print(f"[FILE UPLOAD] {file_info}")
        
        # Reset file pointer after reading
        uploaded_file.seek(0)
        
        if file_type.startswith('image/'):
            # Process image
            base64_image = encode_image_to_base64(uploaded_file)
            if base64_image:
                images.append({
                    'name': file_name,
                    'data': base64_image,
                    'type': file_type
                })
                st.success(f"✅ Processed image: {file_name}")
        
        elif file_type == 'application/pdf':
            # Process PDF
            uploaded_file.seek(0)  # Reset again before PDF processing
            text = extract_text_from_pdf(uploaded_file)
            if text:
                # Validate extracted content
                if SECURITY_MODULES_AVAILABLE:
                    is_safe, reason = validate_file_content(text, 'pdf')
                    if not is_safe:
                        st.error(f"🚫 PDF content check failed for {file_name}: {reason}")
                        continue
                
                text_content.append(f"=== Content from {file_name} ===\n{text}\n")
                st.success(f"✅ Extracted text from PDF: {file_name}")
        
        elif file_type.startswith('text/') or file_name.endswith(('.txt', '.md')):
            # Process text file
            text = file_content.decode('utf-8', errors='ignore')
            
            # Validate text content
            if SECURITY_MODULES_AVAILABLE:
                is_safe, reason = validate_file_content(text, file_ext)
                if not is_safe:
                    st.error(f"🚫 Text content check failed for {file_name}: {reason}")
                    continue
            
            text_content.append(f"=== Content from {file_name} ===\n{text}\n")
            st.success(f"✅ Processed text file: {file_name}")
        
        elif file_name.endswith('.docx'):
            st.warning(f"⚠️ DOCX files not yet supported: {file_name}. Please convert to PDF or copy text manually.")
        
        else:
            st.warning(f"⚠️ Unsupported file type: {file_name} ({file_type})")
    
    return images, text_content

def generate_threat_model(architecture_description, framework="STRIDE", images=None, additional_context="", model_deployment=None):
    """Generate threat model using Azure OpenAI with optional image analysis"""
    
    # Use provided model or fall back to default
    deployment_name = model_deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    # Security: Validate inputs for prompt injection
    if SECURITY_MODULES_AVAILABLE:
        # Check architecture description
        if architecture_description:
            is_safe, reason = detect_prompt_injection(architecture_description)
            if not is_safe:
                st.error(f"🚫 Security check failed: {reason}")
                st.warning("Your input contains patterns that may indicate a prompt injection attack. Please rephrase your architecture description.")
                return None
            
            # Sanitize input
            architecture_description = sanitize_input(architecture_description)
        
        # Check additional context
        if additional_context:
            is_safe, reason = detect_prompt_injection(additional_context)
            if not is_safe:
                st.error(f"🚫 Security check failed on uploaded content: {reason}")
                return None
            
            # Sanitize
            additional_context = sanitize_input(additional_context)
    
    # Ensure clean UTF-8 encoding
    architecture_description = architecture_description.encode('utf-8', errors='ignore').decode('utf-8')
    if additional_context:
        additional_context = additional_context.encode('utf-8', errors='ignore').decode('utf-8')
    
    system_prompt = f"""You are an expert security architect specializing in threat modeling for enterprise applications.

Your task is to analyze the provided architecture and generate a comprehensive threat model using the {framework} methodology.

When analyzing architecture diagrams:
- Identify all components, data flows, and trust boundaries shown
- Note technologies, protocols, and integrations
- Identify entry points and external dependencies
- Look for security controls depicted

Consider the following frameworks and standards:
- AESCSF v2 (Australian Energy Sector Cybersecurity Framework)
- Essential Eight maturity levels
- OWASP Top 10
- CIS Controls
- NIST Cybersecurity Framework

Provide your analysis in the following structured format:

1. **ARCHITECTURE OVERVIEW**
   - Key components identified
   - Trust boundaries
   - Data flows
   - External dependencies

2. **THREAT ANALYSIS (STRIDE)**
   For each component, identify:
   - **S**poofing threats
   - **T**ampering threats
   - **R**epudiation threats
   - **I**nformation Disclosure threats
   - **D**enial of Service threats
   - **E**levation of Privilege threats

3. **RISK ASSESSMENT**
   Rate each threat as:
   - Critical (immediate action required)
   - High (address within 30 days)
   - Medium (address within 90 days)
   - Low (address as resources permit)

4. **MITIGATION STRATEGIES**
   For each high/critical threat, provide:
   - Specific mitigation recommendations
   - Relevant security controls (Essential Eight, AESCSF)
   - Implementation guidance

5. **COMPLIANCE MAPPING**
   Map threats to:
   - AESCSF v2 controls
   - Essential Eight strategies
   - Relevant regulatory requirements

Be specific, actionable, and prioritize based on business impact."""

    # Build user prompt with context
    user_prompt_parts = []
    
    if additional_context:
        user_prompt_parts.append(f"**Additional Context:**\n{additional_context}\n")
    
    if architecture_description:
        user_prompt_parts.append(f"**Architecture Description:**\n{architecture_description}\n")
    
    if not images and not architecture_description and not additional_context:
        return "Please provide architecture description, upload files, or both."
    
    user_prompt_parts.append("\nFocus on practical, actionable security recommendations suitable for an Australian enterprise environment.")
    
    user_prompt = "\n".join(user_prompt_parts)

    try:
        client = get_ai_client()
        
        if not client:
            st.error("Azure OpenAI not configured. Please check application settings.")
            return None
        
        # Clean the prompts for encoding
        system_prompt_clean = system_prompt.encode('utf-8', errors='replace').decode('utf-8')
        user_prompt_clean = user_prompt.encode('utf-8', errors='replace').decode('utf-8')
        
        # Build messages array
        messages = [
            {"role": "system", "content": system_prompt_clean}
        ]
        
        # If images provided, use vision-enabled model format
        if images and len(images) > 0:
            content_parts = [{"type": "text", "text": user_prompt_clean}]
            
            # Add images
            for img in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img['data']}"
                    }
                })
            
            messages.append({
                "role": "user",
                "content": content_parts
            })
        else:
            # Text-only
            messages.append({
                "role": "user",
                "content": user_prompt_clean
            })
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            temperature=0.7,
            max_tokens=4000
        )
        
        return response.choices[0].message.content
    
    except UnicodeEncodeError as e:
        st.error(f"Encoding error: {str(e)}. Please check your input for special characters.")
        return None
    except Exception as e:
        st.error(f"Error generating threat model: {str(e)}")
        st.code(traceback.format_exc())
        return None

def save_threat_model(content, filename):
    """Save threat model to Azure Blob Storage"""
    try:
        blob_service = get_blob_service_client()
        container_client = blob_service.get_container_client(MODELS_CONTAINER)
        
        # Ensure container exists
        try:
            container_client.create_container()
        except:
            pass  # Container already exists
        
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(content, overwrite=True)
        
        return True
    except Exception as e:
        st.error(f"Error saving threat model: {str(e)}")
        return False

# Streamlit UI
st.title("🛡️ AI-Powered Threat Modeling Assistant")
st.markdown("### Accelerate security analysis with Azure OpenAI")

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Check if Azure OpenAI is configured
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY:
        st.error("⚠️ Azure OpenAI not configured!")
        st.markdown("""
        **To use this app, configure these settings:**
        
        1. Portal → App Service → Configuration
        2. Add application settings:
           - `AZURE_OPENAI_ENDPOINT`
           - `AZURE_OPENAI_KEY`
           - `AZURE_OPENAI_DEPLOYMENT`
           - `AZURE_OPENAI_API_VERSION`
        
        See documentation for details.
        """)
        model_configured = False
    else:
        st.success(f"✅ Using: {AZURE_OPENAI_DEPLOYMENT}")
        model_configured = True
    
    # Model selection for comparison
    st.markdown("### AI Model Selection")
    col1, col2 = st.columns(2)
    
    with col1:
        primary_model = st.selectbox(
            "Primary Model",
            ["gpt-4o", "gpt-4", "gpt-4-turbo", "gpt-35-turbo"],
            help="Main model for threat analysis"
        )
    
    with col2:
        compare_enabled = st.checkbox("Compare with second model", help="Generate threat models from two different models for comparison")
        if compare_enabled:
            secondary_model = st.selectbox(
                "Secondary Model",
                ["gpt-4", "gpt-4-turbo", "gpt-35-turbo", "gpt-4o"],
                help="Second model for comparison"
            )
        else:
            secondary_model = None
    
    # Framework selection
    framework = st.selectbox(
        "Threat Modeling Framework",
        ["STRIDE", "PASTA", "LINDDUN", "VAST"]
    )
    
    st.markdown("---")
    st.subheader("About")
    st.markdown("""
    This tool uses Azure OpenAI to automatically generate threat models from architecture descriptions.
    
    **Supported frameworks:**
    - STRIDE (Microsoft)
    - PASTA (Risk-centric)
    - LINDDUN (Privacy)
    - VAST (Business context)
    """)
    
    # Environment info
    with st.expander("Environment Info"):
        st.write(f"**Storage Account:** {STORAGE_ACCOUNT}")
        st.write(f"**OpenAI Endpoint:** {AZURE_OPENAI_ENDPOINT[:50] + '...' if AZURE_OPENAI_ENDPOINT else 'Not set'}")
        st.write(f"**Deployment:** {AZURE_OPENAI_DEPLOYMENT}")
        st.write(f"**Resource Group:** {RESOURCE_GROUP}")

# Main content area
tab1, tab2, tab3, tab4 = st.tabs(["📝 Create Threat Model", "🎨 Diagram Editor", "📚 Saved Models", "ℹ️ Help"])

with tab1:
    st.header("Create New Threat Model")
    
    if not model_configured:
        st.warning("⚠️ Azure OpenAI is not configured. Please configure it in App Service settings to use this feature.")
    else:
        st.markdown("### Upload Architecture Documentation")
        st.markdown("Upload architecture diagrams, solution documents, or design specifications. Supported formats:")
        st.markdown("- **Images**: PNG, JPG, JPEG (architecture diagrams, solution designs)")
        st.markdown("- **Documents**: PDF, TXT, MD (specifications, design docs)")
        
        uploaded_files = st.file_uploader(
            "Upload files (drag and drop multiple files)",
            type=['png', 'jpg', 'jpeg', 'pdf', 'txt', 'md'],
            accept_multiple_files=True,
            help="Upload architecture diagrams and/or documentation. The AI will analyze images and extract text from documents."
        )
        
        # Process uploaded files
        images = []
        extracted_text = ""
        
        if uploaded_files:
            with st.spinner("Processing uploaded files..."):
                images, text_parts = process_uploaded_files(uploaded_files)
                if text_parts:
                    extracted_text = "\n".join(text_parts)
            
            # Show extracted content
            if extracted_text:
                with st.expander("📄 Extracted Text from Documents"):
                    st.text_area("Extracted content", extracted_text, height=200, disabled=True)
            
            if images:
                with st.expander(f"🖼️ Uploaded Images ({len(images)})"):
                    cols = st.columns(min(len(images), 3))
                    for idx, img_data in enumerate(images):
                        with cols[idx % 3]:
                            st.caption(img_data['name'])
                            # Decode and display thumbnail
                            img_bytes = base64.b64decode(img_data['data'])
                            st.image(img_bytes, use_column_width=True)
        
        st.markdown("### Additional Architecture Description")
        st.markdown("Provide additional context or clarification about your architecture:")
        
        architecture_desc = st.text_area(
            "Architecture Description (Optional if files uploaded)",
            height=200,
            placeholder="Describe your architecture including: components, data flows, trust boundaries, authentication mechanisms, external integrations, etc.\n\nOr leave blank if you've uploaded comprehensive documentation.",
            help="You can provide text description, upload files, or both for best results."
        )
        
        # Example templates
        with st.expander("📋 View Example Templates"):
            st.markdown("""
            **Web Application Example:**
            ```
            A customer-facing web portal built on Azure App Service with:
            - React frontend hosted on Azure Static Web Apps
            - .NET Core API backend on App Service
            - Azure SQL Database for customer data
            - Azure AD B2C for authentication
            - Azure Key Vault for secrets
            - Connection to on-premises SAP via Azure VPN Gateway
            - Azure Storage for document uploads
            - Sends notifications via SendGrid
            ```
            
            **Microservices Example:**
            ```
            A microservices architecture on Azure Kubernetes Service with:
            - 10 containerized services (Node.js, Python, Go)
            - Azure Service Bus for async messaging
            - Azure Cosmos DB for document storage
            - Azure Redis Cache for session management
            - Istio service mesh for traffic management
            - Azure Monitor + Application Insights for observability
            - External API integrations (payment gateway, CRM)
            ```
            """)
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            generate_disabled = not model_configured or (not architecture_desc and not uploaded_files)
            button_text = "🔄 Compare Models" if compare_enabled and secondary_model else "🚀 Generate Threat Model"
            
            if st.button(button_text, type="primary", disabled=generate_disabled):
                # Generate from primary model
                with st.spinner(f"Analyzing with {primary_model}..."):
                    threat_model_primary = generate_threat_model(
                        architecture_desc, 
                        framework,
                        images=images,
                        additional_context=extracted_text,
                        model_deployment=primary_model
                    )
                    
                    if threat_model_primary:
                        st.session_state['primary_model'] = primary_model
                        st.session_state['current_threat_model'] = threat_model_primary
                        st.session_state['current_architecture'] = architecture_desc
                        st.session_state['uploaded_files_info'] = [f.name for f in uploaded_files] if uploaded_files else []
                        
                        # Generate from secondary model if comparison enabled
                        if compare_enabled and secondary_model and secondary_model != primary_model:
                            with st.spinner(f"Analyzing with {secondary_model}..."):
                                threat_model_secondary = generate_threat_model(
                                    architecture_desc, 
                                    framework,
                                    images=images,
                                    additional_context=extracted_text,
                                    model_deployment=secondary_model
                                )
                                
                                if threat_model_secondary:
                                    st.session_state['secondary_model'] = secondary_model
                                    st.session_state['secondary_threat_model'] = threat_model_secondary
                                    st.success(f"✅ Threat models generated from {primary_model} and {secondary_model}!")
                                else:
                                    st.warning(f"⚠️ Primary model succeeded, but {secondary_model} failed")
                        else:
                            # Clear secondary if it exists
                            if 'secondary_threat_model' in st.session_state:
                                del st.session_state['secondary_threat_model']
                            if 'secondary_model' in st.session_state:
                                del st.session_state['secondary_model']
                            st.success("✅ Threat model generated successfully!")
        
        with col2:
            if st.button("🔄 Clear"):
                architecture_desc = ""
                uploaded_files = None
                # Clear all session state
                for key in ['current_threat_model', 'uploaded_files_info', 'secondary_threat_model', 'primary_model', 'secondary_model']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
    
    # Display generated threat model(s)
    if 'current_threat_model' in st.session_state:
        st.markdown("---")
        st.header("Generated Threat Model")
        
        # Check if we have comparison results
        has_comparison = 'secondary_threat_model' in st.session_state
        
        if has_comparison:
            # Side-by-side comparison
            st.markdown(f"### Model Comparison: {st.session_state.get('primary_model', 'Model 1')} vs {st.session_state.get('secondary_model', 'Model 2')}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"#### {st.session_state.get('primary_model', 'Primary Model')}")
                st.markdown(st.session_state['current_threat_model'])
            
            with col2:
                st.markdown(f"#### {st.session_state.get('secondary_model', 'Secondary Model')}")
                st.markdown(st.session_state['secondary_threat_model'])
            
            # Save options for comparison
            st.markdown("---")
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = st.text_input("Filename (both models)", value=f"threat_model_comparison_{timestamp}.md")
            
            with col2:
                if st.button("💾 Save Comparison"):
                    # Combine both models
                    combined = f"""# Threat Model Comparison
## Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
## Framework: {framework}

---

# {st.session_state.get('primary_model', 'Model 1')} Analysis

{st.session_state['current_threat_model']}

---

# {st.session_state.get('secondary_model', 'Model 2')} Analysis

{st.session_state['secondary_threat_model']}
"""
                    if save_threat_model(combined, filename):
                        st.success(f"Saved comparison to: {filename}")
            
            with col3:
                st.download_button(
                    "⬇️ Download",
                    combined,
                    file_name=filename,
                    mime="text/markdown"
                )
        else:
            # Single model display
            # Save option
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = st.text_input("Filename", value=f"threat_model_{timestamp}.md")
            
            with col2:
                if st.button("💾 Save to Storage"):
                    if save_threat_model(st.session_state['current_threat_model'], filename):
                        st.success(f"Saved to: {filename}")
            
            with col3:
                st.download_button(
                    "⬇️ Download",
                    st.session_state['current_threat_model'],
                    file_name=filename,
                    mime="text/markdown"
                )
            
            # Display the threat model
            st.markdown(st.session_state['current_threat_model'])
        
        # Download button
        st.download_button(
            label="📥 Download as Markdown",
            data=st.session_state['current_threat_model'],
            file_name=filename,
            mime="text/markdown"
        )

with tab2:
    st.header("🎨 Diagram Editor & Threat Analysis")

    if not DIAGRAM_EDITOR_AVAILABLE:
        st.error("⚠️ Diagram editor modules not available. Ensure `threat_model_diagram_editor.py` and `diagram_threat_integration.py` are in the container.")
    else:
        st.markdown("""
        Create your architecture diagram using the embedded draw.io editor, then generate a threat model directly from it.

        **Workflow:** Draw diagram → Analyse → Generate Threat Model
        """)

        d_tab1, d_tab2, d_tab3 = st.tabs(["🖊️ Diagram Editor", "🔍 Analysis", "📊 Threat Model"])

        with d_tab1:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                editor_height = st.slider("Editor Height (px)", 400, 1200, 700, 50)
            with col2:
                editor_mode = st.radio("Mode", ["Full Featured", "Simple Embed"], horizontal=True)
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔄 Reset", use_container_width=True):
                    for k in ["diagram_xml", "diagram_analysis", "diagram_threat_model"]:
                        st.session_state.pop(k, None)
                    st.rerun()

            st.markdown("---")

            if editor_mode == "Full Featured":
                editor_html = DiagramEditor.render_editor(
                    height=editor_height,
                    initial_diagram=st.session_state.get("diagram_xml"),
                    key="main_editor"
                )
                components.html(editor_html, height=editor_height + 50)
            else:
                simple_drawio_embed(height=editor_height)

            st.markdown("---")
            ul_col, dl_col = st.columns(2)

            with ul_col:
                st.subheader("📁 Load Existing Diagram")
                uploaded_diagram = st.file_uploader(
                    "Upload draw.io XML",
                    type=["xml", "drawio"],
                    help="Upload a previously saved draw.io diagram"
                )
                if uploaded_diagram:
                    diagram_content = uploaded_diagram.read().decode("utf-8")
                    st.session_state["diagram_xml"] = diagram_content
                    st.success("✅ Diagram loaded!")
                    _a = DiagramThreatAnalyzer()
                    if _a.parse_diagram_xml(diagram_content):
                        st.metric("Components", len(_a.elements))
                        st.metric("Data Flows", len(_a.data_flows))

            with dl_col:
                st.subheader("💾 Download Diagram")
                if st.session_state.get("diagram_xml"):
                    st.download_button(
                        "⬇️ Download XML",
                        data=st.session_state["diagram_xml"],
                        file_name=f"diagram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml",
                        mime="text/xml"
                    )
                else:
                    st.info("Create or load a diagram to enable download")

        with d_tab2:
            st.header("🔍 Diagram Analysis")
            if not st.session_state.get("diagram_xml"):
                st.warning("⚠️ No diagram loaded. Upload or create one in the **Diagram Editor** tab first.")
            else:
                _, btn_col = st.columns([4, 1])
                with btn_col:
                    if st.button("🔍 Analyse", type="primary", use_container_width=True):
                        with st.spinner("Analysing diagram structure..."):
                            analysis = integrate_diagram_with_ai(
                                st.session_state["diagram_xml"],
                                framework=framework
                            )
                            st.session_state["diagram_analysis"] = analysis

                if st.session_state.get("diagram_analysis"):
                    _analysis = st.session_state["diagram_analysis"]
                    if _analysis.get("success"):
                        _stats = _analysis.get("statistics", {})
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Components", _stats.get("elements", 0))
                        c2.metric("Data Flows", _stats.get("flows", 0))
                        c3.metric("Trust Boundaries", _stats.get("boundaries", 0))

                        st.markdown("### 📝 Generated System Description")
                        st.text_area(
                            "This is sent to AI as context",
                            value=_analysis.get("system_description", ""),
                            height=200,
                            disabled=True
                        )

                        if _analysis.get("analysis_hints"):
                            st.markdown("### ⚠️ Initial Risk Indicators")
                            for _cat, _hints in _analysis["analysis_hints"].items():
                                with st.expander(f"⚠️ {_cat}"):
                                    for _h in _hints:
                                        st.warning(_h)

                        with st.expander("🔍 Raw Parsed Diagram Data"):
                            st.json(_analysis.get("diagram_json", "{}"))

                        st.markdown("---")
                        if st.button("🚀 Generate Threat Model from Diagram", type="primary", use_container_width=True):
                            st.session_state["run_diagram_tm"] = True
                            st.rerun()
                    else:
                        st.error(f"❌ Analysis failed: {_analysis.get('error', 'Unknown error')}")
                else:
                    st.info("👆 Click **Analyse** to parse your diagram")

        with d_tab3:
            st.header("📊 Diagram-Based Threat Model")

            if st.session_state.pop("run_diagram_tm", False):
                _analysis = st.session_state.get("diagram_analysis", {})
                _ai_prompt = _analysis.get("ai_prompt", "")
                if _ai_prompt:
                    with st.spinner("🤖 Generating threat model from diagram..."):
                        _tm = generate_threat_model(_ai_prompt, framework)
                        if _tm:
                            st.session_state["diagram_threat_model"] = _tm
                            st.success("✅ Threat model generated!")
                else:
                    st.error("No diagram analysis found — please run Analysis first.")

            if st.session_state.get("diagram_threat_model"):
                _tm_result = st.session_state["diagram_threat_model"]
                _, _dl_col = st.columns([3, 1])
                with _dl_col:
                    st.download_button(
                        "⬇️ Download Markdown",
                        data=_tm_result,
                        file_name=f"diagram_threat_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
                st.markdown(_tm_result)
            else:
                st.info("""
                💡 **No threat model yet**

                1. Draw or upload a diagram in the **Diagram Editor** tab
                2. Click **Analyse** in the Analysis tab
                3. Click **Generate Threat Model from Diagram**
                """)

with tab3:
    st.header("Saved Threat Models")
    
    try:
        blob_service = get_blob_service_client()
        container_client = blob_service.get_container_client(MODELS_CONTAINER)
        
        blobs = list(container_client.list_blobs())
        
        if blobs:
            st.write(f"Found {len(blobs)} saved threat models:")
            
            for blob in sorted(blobs, key=lambda x: x.last_modified, reverse=True):
                with st.expander(f"📄 {blob.name} - {blob.last_modified.strftime('%Y-%m-%d %H:%M')}"):
                    blob_client = container_client.get_blob_client(blob.name)
                    content = blob_client.download_blob().readall().decode('utf-8')
                    st.markdown(content)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            "Download",
                            data=content,
                            file_name=blob.name,
                            mime="text/markdown",
                            key=f"download_{blob.name}"
                        )
                    with col2:
                        if st.button("Delete", key=f"delete_{blob.name}"):
                            blob_client.delete_blob()
                            st.success(f"Deleted {blob.name}")
                            st.rerun()
        else:
            st.info("No saved threat models yet. Create one in the 'Create Threat Model' tab!")
    
    except Exception as e:
        st.error(f"Error loading saved models: {str(e)}")

with tab4:
    st.header("How to Use This Tool")
    
    st.markdown("""
    ### Getting Started
    
    1. **Ensure Azure OpenAI is configured**: Check the sidebar for configuration status
    2. **Describe Architecture**: Provide a detailed description of your system
    3. **Generate**: Click the button to generate your threat model
    4. **Review & Save**: Review the analysis and save it to Azure Storage
    
    ### Best Practices
    
    **For Best Results, Include:**
    - All system components (databases, APIs, services)
    - Authentication and authorization mechanisms
    - Data flows and trust boundaries
    - External integrations and dependencies
    - Compliance requirements (AESCSF, Essential Eight)
    
    **Example Architecture Description:**
    ```
    A three-tier web application consisting of:
    - Frontend: React SPA on Azure Static Web Apps
    - Backend: .NET Core API on Azure App Service (Linux)
    - Database: Azure SQL Database with private endpoint
    - Authentication: Azure AD with MFA
    - Secrets: Azure Key Vault
    - File Storage: Azure Blob Storage with SAS tokens
    - External: Integration with Salesforce via REST API
    - Monitoring: Application Insights
    
    Trust boundaries:
    - Public internet to Azure Front Door
    - Front Door to App Service (private endpoint)
    - App Service to SQL (private endpoint)
    - App Service to Salesforce (public internet)
    ```
    
    ### Framework Descriptions
    
    - **STRIDE**: Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege
    - **PASTA**: Process for Attack Simulation and Threat Analysis
    - **LINDDUN**: Privacy-focused threat modeling
    - **VAST**: Visual, Agile, and Simple Threat modeling
    
    ### Australian Compliance
    
    The tool automatically considers:
    - AESCSF v2 (Australian Energy Sector Cybersecurity Framework)
    - Essential Eight strategies
    - Privacy Act requirements
    - SOCI Act (Security of Critical Infrastructure)
    
    ### Cost Optimization Tips
    
    - Azure OpenAI costs ~$5-10 per 1M tokens
    - Average threat model: ~10K-50K tokens = $0.50-$2.00 each
    - Save frequently used architectures as templates
    - Reuse threat models for similar systems
    
    ### Need Help?
    
    Contact your security team or check the project documentation.
    """)

# Footer with version
st.markdown("---")
version = os.getenv("APP_VERSION", "dev")
git_sha = os.getenv("GIT_SHA", "unknown")
st.markdown(f"🛡️ **AI Threat Modeling POC** | Powered by Azure OpenAI | Built with Streamlit | Version: `{version}` | Commit: `{git_sha[:7]}`")

