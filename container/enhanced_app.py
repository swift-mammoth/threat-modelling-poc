"""
Enhanced Threat Modelling Application with Embedded Draw.io Editor
Integrates visual diagram creation with AI-powered threat analysis
"""

import streamlit as st
import os
from datetime import datetime
import json

# Import our custom components
from threat_model_diagram_editor import (
    DiagramEditor,
    render_diagram_editor_tab,
    simple_drawio_embed
)
from diagram_threat_integration import (
    integrate_diagram_with_ai,
    DiagramThreatAnalyzer
)

# Page configuration
st.set_page_config(
    page_title="AI Threat Modelling Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'current_diagram' not in st.session_state:
    st.session_state.current_diagram = None
if 'threat_model_results' not in st.session_state:
    st.session_state.threat_model_results = None
if 'diagram_analysis' not in st.session_state:
    st.session_state.diagram_analysis = None


def main():
    """Main application entry point"""
    
    # Sidebar
    with st.sidebar:
        st.title("🛡️ Threat Modelling Assistant")
        st.markdown("---")
        
        # Mode selection
        mode = st.radio(
            "Select Input Mode",
            [
                "🎨 Interactive Diagram",
                "📝 Text Description",
                "🖼️ Upload Image",
                "📄 Upload PDF"
            ]
        )
        
        st.markdown("---")
        
        # Framework selection
        framework = st.selectbox(
            "Threat Modelling Framework",
            [
                "STRIDE",
                "PASTA",
                "LINDDUN",
                "VAST",
                "Attack Trees",
                "Kill Chains"
            ],
            help="Select the framework for threat analysis"
        )
        
        # Compliance requirements
        st.markdown("### 🏛️ Compliance Requirements")
        compliance = st.multiselect(
            "Select applicable frameworks",
            [
                "AESCSF v2 (Australian)",
                "Essential Eight",
                "NIST CSF",
                "ISO 27001",
                "PCI DSS",
                "GDPR",
                "HIPAA"
            ]
        )
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            detail_level = st.select_slider(
                "Analysis Detail Level",
                options=["Basic", "Standard", "Detailed", "Comprehensive"],
                value="Standard"
            )
            
            include_mitigations = st.checkbox(
                "Include Mitigations",
                value=True
            )
            
            include_attack_paths = st.checkbox(
                "Include Attack Paths",
                value=True
            )
        
        st.markdown("---")
        st.caption(f"Version: {get_app_version()}")
    
    # Main content area
    st.title("🛡️ AI-Powered Threat Modelling")
    
    # Tab selection based on mode
    if "Interactive Diagram" in mode:
        render_diagram_mode(framework, compliance, detail_level)
    elif "Text Description" in mode:
        render_text_mode(framework, compliance)
    elif "Upload Image" in mode:
        render_image_upload_mode(framework, compliance)
    elif "Upload PDF" in mode:
        render_pdf_upload_mode(framework, compliance)


def render_diagram_mode(framework: str, compliance: list, detail_level: str):
    """Render the interactive diagram editing and analysis mode"""
    
    tab1, tab2, tab3 = st.tabs([
        "📐 Diagram Editor",
        "🔍 Analysis",
        "📊 Threat Model"
    ])
    
    with tab1:
        st.header("🎨 Interactive Diagram Editor")
        
        st.markdown("""
        Create your system architecture diagram using the embedded draw.io editor.
        
        **Quick Start:**
        1. Use the shape libraries to add components (processes, data stores, external entities)
        2. Connect components with arrows to show data flows
        3. Add trust boundaries using dashed rectangles
        4. Label everything clearly
        5. Click 'Analyze Diagram' when ready
        """)
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            editor_height = st.slider(
                "Editor Height",
                min_value=400,
                max_value=1200,
                value=700,
                step=50
            )
        
        with col2:
            editor_mode = st.radio(
                "Editor Mode",
                ["Full Featured", "Simple Embed"],
                horizontal=True,
                help="Full Featured provides more control, Simple Embed is faster"
            )
        
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.current_diagram = None
                st.session_state.diagram_analysis = None
                st.rerun()
        
        st.markdown("---")
        
        # Render appropriate editor
        if editor_mode == "Full Featured":
            # Full featured editor with messaging
            editor_html = DiagramEditor.render_editor(
                height=editor_height,
                initial_diagram=st.session_state.current_diagram,
                key="main_editor"
            )
            st.components.v1.html(editor_html, height=editor_height + 50)
        else:
            # Simple embed
            simple_drawio_embed(height=editor_height)
        
        # File operations
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📁 Load Diagram")
            uploaded_file = st.file_uploader(
                "Upload existing diagram",
                type=['xml', 'drawio'],
                help="Upload a draw.io diagram to continue editing"
            )
            
            if uploaded_file:
                diagram_content = uploaded_file.read().decode('utf-8')
                st.session_state.current_diagram = diagram_content
                st.success("✅ Diagram loaded!")
                
                # Quick preview
                analyzer = DiagramThreatAnalyzer()
                if analyzer.parse_diagram_xml(diagram_content):
                    st.metric("Components", len(analyzer.elements))
                    st.metric("Data Flows", len(analyzer.data_flows))
        
        with col2:
            st.subheader("💾 Save Diagram")
            if st.session_state.current_diagram:
                st.download_button(
                    label="⬇️ Download Diagram XML",
                    data=st.session_state.current_diagram,
                    file_name=f"threat_model_diagram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml",
                    mime="text/xml"
                )
            else:
                st.info("Create or load a diagram first")
    
    with tab2:
        st.header("🔍 Diagram Analysis")
        
        if st.session_state.current_diagram:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("### Current Diagram Overview")
            
            with col2:
                if st.button("🔍 Analyze Diagram", use_container_width=True, type="primary"):
                    with st.spinner("Analyzing diagram structure..."):
                        analysis = integrate_diagram_with_ai(
                            st.session_state.current_diagram,
                            framework=framework,
                            compliance_requirements=compliance
                        )
                        st.session_state.diagram_analysis = analysis
            
            # Show analysis results
            if st.session_state.diagram_analysis:
                analysis = st.session_state.diagram_analysis
                
                if analysis.get('success'):
                    # Statistics
                    st.markdown("### 📊 Diagram Statistics")
                    col1, col2, col3 = st.columns(3)
                    
                    stats = analysis.get('statistics', {})
                    with col1:
                        st.metric("Components", stats.get('elements', 0))
                    with col2:
                        st.metric("Data Flows", stats.get('flows', 0))
                    with col3:
                        st.metric("Trust Boundaries", stats.get('boundaries', 0))
                    
                    # System description
                    st.markdown("### 📝 System Description")
                    st.text_area(
                        "Generated description for AI analysis",
                        value=analysis.get('system_description', ''),
                        height=200,
                        disabled=True
                    )
                    
                    # Analysis hints
                    if analysis.get('analysis_hints'):
                        st.markdown("### 💡 Initial Risk Indicators")
                        for category, hints in analysis['analysis_hints'].items():
                            with st.expander(f"⚠️ {category}"):
                                for hint in hints:
                                    st.warning(hint)
                    
                    # Diagram JSON
                    with st.expander("🔍 View Parsed Diagram Data"):
                        st.json(analysis.get('diagram_json', '{}'))
                    
                    st.markdown("---")
                    
                    # Generate threat model button
                    if st.button(
                        "🚀 Generate Threat Model from Diagram",
                        use_container_width=True,
                        type="primary"
                    ):
                        st.session_state['switch_to_threat_model'] = True
                        st.rerun()
                else:
                    st.error(f"❌ Analysis failed: {analysis.get('error', 'Unknown error')}")
            else:
                st.info("👆 Click 'Analyze Diagram' to start the analysis")
        else:
            st.warning("⚠️ No diagram loaded. Please create or upload a diagram in the Editor tab.")
    
    with tab3:
        st.header("📊 Threat Model Results")
        
        # Check if we should trigger threat model generation
        if st.session_state.get('switch_to_threat_model'):
            st.session_state['switch_to_threat_model'] = False
            generate_threat_model_from_diagram(framework, compliance)
        
        # Display threat model results
        if st.session_state.threat_model_results:
            display_threat_model_results(st.session_state.threat_model_results)
        else:
            st.info("""
            💡 **No threat model generated yet**
            
            1. Create your diagram in the **Diagram Editor** tab
            2. Analyze it in the **Analysis** tab
            3. Generate the threat model to see results here
            """)


def generate_threat_model_from_diagram(framework: str, compliance: list):
    """Generate threat model using AI based on diagram analysis"""
    
    if not st.session_state.diagram_analysis:
        st.error("Please analyze the diagram first")
        return
    
    analysis = st.session_state.diagram_analysis
    
    with st.spinner(f"🤖 Generating {framework} threat model..."):
        # This would integrate with your existing Azure OpenAI logic
        # For now, we'll create a placeholder
        
        ai_prompt = analysis.get('ai_prompt', '')
        
        # Placeholder for actual AI call
        # In your actual implementation, you would call:
        # response = call_azure_openai(ai_prompt, framework, compliance)
        
        # Mock result for demonstration
        threat_model = {
            'framework': framework,
            'timestamp': datetime.now().isoformat(),
            'system_description': analysis.get('system_description', ''),
            'threats': generate_mock_threats(analysis, framework),
            'compliance': compliance,
            'diagram_stats': analysis.get('statistics', {})
        }
        
        st.session_state.threat_model_results = threat_model
        st.success("✅ Threat model generated successfully!")


def generate_mock_threats(analysis: dict, framework: str) -> list:
    """Generate mock threats based on diagram analysis (placeholder)"""
    hints = analysis.get('analysis_hints', {})
    threats = []
    
    for category, hint_list in hints.items():
        for hint in hint_list:
            threats.append({
                'category': category,
                'description': hint,
                'severity': 'High',
                'likelihood': 'Medium',
                'mitigation': 'Implement appropriate controls based on risk assessment'
            })
    
    return threats


def display_threat_model_results(results: dict):
    """Display threat model results with formatting"""
    
    st.markdown("### 📋 Threat Model Summary")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Framework", results['framework'])
    with col2:
        st.metric("Total Threats", len(results.get('threats', [])))
    with col3:
        st.metric("Components Analyzed", results.get('diagram_stats', {}).get('elements', 0))
    
    # Threats table
    st.markdown("### ⚠️ Identified Threats")
    
    threats = results.get('threats', [])
    if threats:
        for i, threat in enumerate(threats, 1):
            with st.expander(f"🔴 Threat #{i}: {threat['category']}"):
                st.markdown(f"**Description:** {threat['description']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Severity:** {threat['severity']}")
                with col2:
                    st.markdown(f"**Likelihood:** {threat['likelihood']}")
                
                st.markdown(f"**Mitigation:** {threat['mitigation']}")
    else:
        st.info("No threats identified")
    
    # Download options
    st.markdown("---")
    st.markdown("### 💾 Export Results")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Export as JSON
        json_export = json.dumps(results, indent=2)
        st.download_button(
            label="📥 Download as JSON",
            data=json_export,
            file_name=f"threat_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with col2:
        # Export as Markdown
        md_export = generate_markdown_report(results)
        st.download_button(
            label="📥 Download as Markdown",
            data=md_export,
            file_name=f"threat_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )


def generate_markdown_report(results: dict) -> str:
    """Generate markdown formatted report"""
    lines = [
        f"# Threat Model Report",
        f"",
        f"**Generated:** {results['timestamp']}",
        f"**Framework:** {results['framework']}",
        f"",
        f"## System Architecture",
        f"",
        results.get('system_description', ''),
        f"",
        f"## Identified Threats",
        f""
    ]
    
    for i, threat in enumerate(results.get('threats', []), 1):
        lines.extend([
            f"### Threat #{i}: {threat['category']}",
            f"",
            f"**Description:** {threat['description']}",
            f"**Severity:** {threat['severity']}",
            f"**Likelihood:** {threat['likelihood']}",
            f"**Mitigation:** {threat['mitigation']}",
            f""
        ])
    
    return "\n".join(lines)


def render_text_mode(framework: str, compliance: list):
    """Render text description input mode"""
    st.header("📝 Describe Your System")
    
    system_description = st.text_area(
        "System Description",
        height=300,
        placeholder="Describe your system architecture, components, data flows, and security requirements...",
        help="Provide a detailed description of your system for threat analysis"
    )
    
    if st.button("Generate Threat Model", type="primary") and system_description:
        st.info("🚧 Text-based threat modeling integration coming soon!")


def render_image_upload_mode(framework: str, compliance: list):
    """Render image upload mode"""
    st.header("🖼️ Upload Architecture Diagram")
    
    uploaded_file = st.file_uploader(
        "Upload diagram image",
        type=['png', 'jpg', 'jpeg'],
        help="Upload an architecture diagram for analysis"
    )
    
    if uploaded_file:
        st.image(uploaded_file, caption="Uploaded Diagram", use_container_width=True)
        
        if st.button("Analyze Diagram", type="primary"):
            st.info("🚧 Image-based analysis integration coming soon!")


def render_pdf_upload_mode(framework: str, compliance: list):
    """Render PDF upload mode"""
    st.header("📄 Upload PDF Documentation")
    
    uploaded_file = st.file_uploader(
        "Upload PDF documentation",
        type=['pdf'],
        help="Upload architectural documentation in PDF format"
    )
    
    if uploaded_file:
        st.success(f"✅ Uploaded: {uploaded_file.name}")
        
        if st.button("Analyze PDF", type="primary"):
            st.info("🚧 PDF analysis integration coming soon!")


def get_app_version() -> str:
    """Get application version from environment or Git"""
    version = os.getenv('APP_VERSION', 'dev')
    git_sha = os.getenv('GIT_SHA', 'local')
    return f"{version} ({git_sha[:7]})"


if __name__ == "__main__":
    main()
