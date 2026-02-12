"""
Threat Model Diagram Editor Component
Embeds draw.io for real-time diagram creation with threat modelling integration
"""

import streamlit as st
import streamlit.components.v1 as components
import base64
import json
from typing import Optional, Dict, Any
import xml.etree.ElementTree as ET

class DiagramEditor:
    """
    Embedded draw.io diagram editor for threat modelling
    """
    
    # Draw.io embed URL - using the official diagrams.net embed version
    DRAWIO_EMBED_URL = "https://embed.diagrams.net/"
    
    # Threat modelling shape libraries
    THREAT_MODEL_LIBRARIES = [
        "general",
        "aws4",
        "azure",
        "gcp2",
        "security",
        "network",
        "c4",
        "threat_modelling"  # Custom library if created
    ]
    
    @staticmethod
    def create_embed_config(
        diagram_xml: Optional[str] = None,
        ui_theme: str = "atlas",
        libraries: list = None
    ) -> Dict[str, Any]:
        """
        Create draw.io embed configuration
        
        Args:
            diagram_xml: Optional existing diagram XML
            ui_theme: draw.io theme (atlas, kennedy, dark, min)
            libraries: List of shape libraries to enable
            
        Returns:
            Configuration dict for draw.io embed
        """
        if libraries is None:
            libraries = DiagramEditor.THREAT_MODEL_LIBRARIES
            
        config = {
            "ui": ui_theme,
            "spin": True,
            "libraries": True,
            "saveAndExit": True,
            "noSaveBtn": False,
            "noExitBtn": False,
            "configure": True,
            "libs": ";".join(libraries),
            "chrome": 0,  # Minimal chrome
            "nav": 1,  # Enable navigation
            "toolbar": "1",  # Show toolbar
        }
        
        if diagram_xml:
            # Encode existing diagram
            encoded = base64.b64encode(diagram_xml.encode()).decode()
            config["xml"] = encoded
            
        return config
    
    @staticmethod
    def render_editor(
        height: int = 800,
        initial_diagram: Optional[str] = None,
        key: str = "diagram_editor"
    ) -> str:
        """
        Render the draw.io embedded editor
        
        Args:
            height: Height of the editor in pixels
            initial_diagram: Optional XML of initial diagram
            key: Unique key for the component
            
        Returns:
            HTML for embedding draw.io
        """
        config = DiagramEditor.create_embed_config(
            diagram_xml=initial_diagram,
            ui_theme="atlas"
        )
        
        # Build URL with parameters
        params = "&".join([f"{k}={v}" for k, v in config.items()])
        embed_url = f"{DiagramEditor.DRAWIO_EMBED_URL}?{params}"
        
        # Create HTML for iframe with messaging
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ margin: 0; padding: 0; overflow: hidden; }}
                #drawio-container {{ width: 100%; height: {height}px; border: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <iframe 
                id="drawio-container"
                src="{embed_url}"
                frameborder="0"
            ></iframe>
            
            <script>
                // Handle messages from draw.io
                window.addEventListener('message', function(evt) {{
                    if (evt.data.length > 0) {{
                        try {{
                            var msg = JSON.parse(evt.data);
                            
                            // Handle different message types
                            if (msg.event === 'init') {{
                                console.log('Draw.io initialized');
                            }}
                            else if (msg.event === 'save') {{
                                // Diagram saved
                                console.log('Diagram saved');
                                // Send data back to Streamlit
                                window.parent.postMessage({{
                                    type: 'diagram_saved',
                                    xml: msg.xml
                                }}, '*');
                            }}
                            else if (msg.event === 'export') {{
                                // Diagram exported
                                console.log('Diagram exported');
                            }}
                            else if (msg.event === 'exit') {{
                                console.log('Editor closed');
                            }}
                        }} catch(e) {{
                            console.log('Non-JSON message:', evt.data);
                        }}
                    }}
                }});
                
                // Send configuration to draw.io
                var iframe = document.getElementById('drawio-container');
                iframe.addEventListener('load', function() {{
                    // Configure draw.io after load
                    iframe.contentWindow.postMessage(
                        JSON.stringify({{action: 'load'}}),
                        '*'
                    );
                }});
            </script>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def extract_threat_model_elements(diagram_xml: str) -> Dict[str, Any]:
        """
        Extract threat model elements from draw.io XML
        
        Args:
            diagram_xml: Draw.io XML diagram
            
        Returns:
            Dictionary of threat model elements
        """
        try:
            root = ET.fromstring(diagram_xml)
            
            elements = {
                "processes": [],
                "data_stores": [],
                "external_entities": [],
                "data_flows": [],
                "trust_boundaries": []
            }
            
            # Parse mxCell elements
            for cell in root.iter('mxCell'):
                value = cell.get('value', '')
                style = cell.get('style', '')
                
                # Identify element types based on style
                if 'ellipse' in style or 'process' in style.lower():
                    elements["processes"].append({
                        "id": cell.get('id'),
                        "name": value,
                        "style": style
                    })
                elif 'cylinder' in style or 'datastore' in style.lower():
                    elements["data_stores"].append({
                        "id": cell.get('id'),
                        "name": value,
                        "style": style
                    })
                elif 'actor' in style.lower() or 'external' in value.lower():
                    elements["external_entities"].append({
                        "id": cell.get('id'),
                        "name": value,
                        "style": style
                    })
                elif cell.get('edge') == '1':
                    elements["data_flows"].append({
                        "id": cell.get('id'),
                        "label": value,
                        "source": cell.get('source'),
                        "target": cell.get('target')
                    })
                elif 'dashed' in style or 'boundary' in value.lower():
                    elements["trust_boundaries"].append({
                        "id": cell.get('id'),
                        "name": value
                    })
            
            return elements
            
        except Exception as e:
            st.error(f"Error parsing diagram: {str(e)}")
            return {}


def render_diagram_editor_tab():
    """
    Render the diagram editor tab in Streamlit
    """
    st.header("🎨 Interactive Diagram Editor")
    
    st.markdown("""
    Create your architecture diagram using the embedded draw.io editor below.
    Use threat modelling shapes and components to build your system architecture.
    
    **Features:**
    - Full draw.io functionality
    - Threat modelling shape libraries (AWS, Azure, GCP, Security)
    - Save diagrams for threat analysis
    - Export to XML, PNG, SVG
    """)
    
    # Editor options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        editor_height = st.slider(
            "Editor Height (px)",
            min_value=400,
            max_value=1200,
            value=800,
            step=50
        )
    
    with col2:
        if st.button("🔄 Reset Diagram"):
            if 'current_diagram' in st.session_state:
                del st.session_state.current_diagram
            st.rerun()
    
    with col3:
        if st.button("📊 Analyze Current Diagram"):
            if 'current_diagram' in st.session_state:
                st.session_state['analyze_diagram'] = True
    
    # Load existing diagram if available
    initial_diagram = st.session_state.get('current_diagram', None)
    
    # Render the editor
    editor_html = DiagramEditor.render_editor(
        height=editor_height,
        initial_diagram=initial_diagram,
        key="main_diagram_editor"
    )
    
    components.html(editor_html, height=editor_height + 50)
    
    # File upload for existing diagrams
    st.markdown("---")
    st.subheader("📁 Load Existing Diagram")
    
    uploaded_file = st.file_uploader(
        "Upload draw.io XML file",
        type=['xml', 'drawio'],
        help="Upload an existing draw.io diagram to continue editing"
    )
    
    if uploaded_file:
        diagram_content = uploaded_file.read().decode('utf-8')
        st.session_state['current_diagram'] = diagram_content
        st.success("✅ Diagram loaded! Click 'Reset Diagram' to refresh the editor.")
        
        # Show preview of elements
        with st.expander("📋 Diagram Elements Preview"):
            elements = DiagramEditor.extract_threat_model_elements(diagram_content)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Processes", len(elements.get('processes', [])))
                st.metric("Data Stores", len(elements.get('data_stores', [])))
                st.metric("External Entities", len(elements.get('external_entities', [])))
            
            with col2:
                st.metric("Data Flows", len(elements.get('data_flows', [])))
                st.metric("Trust Boundaries", len(elements.get('trust_boundaries', [])))
    
    # Show analysis section if triggered
    if st.session_state.get('analyze_diagram', False):
        st.markdown("---")
        st.subheader("🔍 Diagram Analysis")
        
        if 'current_diagram' in st.session_state:
            elements = DiagramEditor.extract_threat_model_elements(
                st.session_state['current_diagram']
            )
            
            st.json(elements)
            
            if st.button("🚀 Generate Threat Model from Diagram"):
                st.info("Integration with threat model generation coming next!")
                # This would integrate with your existing threat model generation
        else:
            st.warning("No diagram available for analysis. Create or load a diagram first.")
        
        st.session_state['analyze_diagram'] = False


# Alternative: Simpler iframe embed for quick integration
def simple_drawio_embed(height: int = 800) -> None:
    """
    Simple draw.io embed without complex messaging
    Good for quick prototyping
    """
    embed_url = (
        "https://embed.diagrams.net/"
        "?embed=1&ui=atlas&spin=1&libraries=1&proto=json"
        "&saveAndExit=1&noSaveBtn=0&noExitBtn=0"
    )
    
    html = f"""
    <iframe 
        src="{embed_url}" 
        width="100%" 
        height="{height}px" 
        frameborder="0"
        style="border: 1px solid #ddd; border-radius: 4px;"
    ></iframe>
    """
    
    components.html(html, height=height + 10)


if __name__ == "__main__":
    # Test the component
    st.set_page_config(
        page_title="Threat Model Diagram Editor",
        page_icon="🎨",
        layout="wide"
    )
    
    render_diagram_editor_tab()
