"""
Integration Module: Connect Draw.io Diagrams with AI Threat Model Generation
Analyzes diagram structure and generates comprehensive threat models
"""

import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import streamlit as st


@dataclass
class ThreatModelElement:
    """Represents a threat model element extracted from diagram"""
    id: str
    name: str
    element_type: str
    trust_level: str = "unknown"
    description: str = ""
    technologies: List[str] = None
    
    def __post_init__(self):
        if self.technologies is None:
            self.technologies = []


@dataclass
class DataFlow:
    """Represents a data flow between elements"""
    id: str
    source_id: str
    target_id: str
    label: str = ""
    protocol: str = "unknown"
    data_classification: str = "unknown"
    encrypted: bool = False


class DiagramThreatAnalyzer:
    """
    Analyzes draw.io diagrams and prepares them for AI threat modelling
    """
    
    # Element type detection patterns
    ELEMENT_PATTERNS = {
        'process': ['ellipse', 'process', 'roundRectangle', 'service', 'api'],
        'data_store': ['cylinder', 'database', 'storage', 'datastore'],
        'external_entity': ['actor', 'user', 'external', 'cloud', 'thirdparty'],
        'trust_boundary': ['dashed', 'boundary', 'dotted', 'perimeter'],
    }
    
    # Technology detection keywords
    TECH_KEYWORDS = {
        'aws': ['s3', 'ec2', 'lambda', 'rds', 'dynamodb', 'api gateway', 'cloudfront'],
        'azure': ['blob', 'cosmos', 'function', 'app service', 'sql database'],
        'gcp': ['storage', 'compute', 'cloud function', 'cloud sql'],
        'container': ['docker', 'kubernetes', 'k8s', 'container', 'pod'],
        'api': ['rest', 'graphql', 'api', 'endpoint', 'webhook'],
        'auth': ['oauth', 'saml', 'jwt', 'authentication', 'authorization'],
        'database': ['sql', 'nosql', 'mongodb', 'postgresql', 'mysql', 'redis'],
    }
    
    def __init__(self):
        self.elements: List[ThreatModelElement] = []
        self.data_flows: List[DataFlow] = []
        self.trust_boundaries: List[str] = []
    
    def parse_diagram_xml(self, xml_content: str) -> bool:
        """
        Parse draw.io XML and extract threat model elements
        
        Args:
            xml_content: Raw XML content from draw.io
            
        Returns:
            True if parsing successful
        """
        try:
            root = ET.fromstring(xml_content)
            
            # Clear previous data
            self.elements.clear()
            self.data_flows.clear()
            self.trust_boundaries.clear()
            
            # Track all cells for reference
            cells_by_id = {}
            
            # First pass: collect all cells
            for cell in root.iter('mxCell'):
                cell_id = cell.get('id')
                if cell_id:
                    cells_by_id[cell_id] = cell
            
            # Second pass: process cells
            for cell in root.iter('mxCell'):
                cell_id = cell.get('id')
                if not cell_id or cell_id in ['0', '1']:  # Skip root cells
                    continue
                
                value = cell.get('value', '').strip()
                style = cell.get('style', '').lower()
                
                # Check if it's an edge (data flow)
                if cell.get('edge') == '1':
                    self._process_data_flow(cell, value)
                # Check if it's a trust boundary
                elif self._is_trust_boundary(style, value):
                    self.trust_boundaries.append(value or f"Boundary_{cell_id}")
                # Otherwise process as an element
                else:
                    element = self._process_element(cell, value, style)
                    if element:
                        self.elements.append(element)
            
            return True
            
        except Exception as e:
            st.error(f"Error parsing diagram XML: {str(e)}")
            return False
    
    def _process_element(
        self,
        cell: ET.Element,
        value: str,
        style: str
    ) -> Optional[ThreatModelElement]:
        """Process a single diagram element"""
        cell_id = cell.get('id')
        
        # Determine element type
        element_type = self._determine_element_type(style, value)
        
        # Extract technologies
        technologies = self._extract_technologies(value, style)
        
        # Determine trust level (simplified - could be enhanced)
        trust_level = self._determine_trust_level(element_type, technologies)
        
        return ThreatModelElement(
            id=cell_id,
            name=value or f"{element_type}_{cell_id}",
            element_type=element_type,
            trust_level=trust_level,
            technologies=technologies
        )
    
    def _process_data_flow(self, cell: ET.Element, label: str) -> None:
        """Process a data flow edge"""
        flow = DataFlow(
            id=cell.get('id'),
            source_id=cell.get('source', ''),
            target_id=cell.get('target', ''),
            label=label,
            protocol=self._detect_protocol(label),
            encrypted=self._detect_encryption(label)
        )
        self.data_flows.append(flow)
    
    def _determine_element_type(self, style: str, value: str) -> str:
        """Determine the type of element based on style and value"""
        combined = (style + ' ' + value).lower()
        
        for element_type, patterns in self.ELEMENT_PATTERNS.items():
            if any(pattern in combined for pattern in patterns):
                return element_type
        
        return 'process'  # Default
    
    def _extract_technologies(self, value: str, style: str) -> List[str]:
        """Extract technology stack from element name and style"""
        combined = (value + ' ' + style).lower()
        technologies = []
        
        for tech, keywords in self.TECH_KEYWORDS.items():
            if any(keyword in combined for keyword in keywords):
                technologies.append(tech)
        
        return technologies
    
    def _determine_trust_level(
        self,
        element_type: str,
        technologies: List[str]
    ) -> str:
        """Determine trust level based on element characteristics"""
        if element_type == 'external_entity':
            return 'untrusted'
        elif 'cloud' in technologies or 'external' in element_type:
            return 'semi-trusted'
        else:
            return 'trusted'
    
    def _is_trust_boundary(self, style: str, value: str) -> bool:
        """Check if element represents a trust boundary"""
        combined = (style + ' ' + value).lower()
        patterns = self.ELEMENT_PATTERNS['trust_boundary']
        return any(pattern in combined for pattern in patterns)
    
    def _detect_protocol(self, label: str) -> str:
        """Detect protocol from data flow label"""
        label_lower = label.lower()
        
        protocols = {
            'https': ['https', 'tls', 'ssl'],
            'http': ['http'],
            'grpc': ['grpc'],
            'sql': ['sql'],
            'nosql': ['nosql'],
            'message_queue': ['mq', 'kafka', 'rabbitmq', 'queue'],
        }
        
        for protocol, keywords in protocols.items():
            if any(kw in label_lower for kw in keywords):
                return protocol
        
        return 'unknown'
    
    def _detect_encryption(self, label: str) -> bool:
        """Detect if data flow indicates encryption"""
        label_lower = label.lower()
        encryption_indicators = ['https', 'tls', 'ssl', 'encrypted', 'secure']
        return any(indicator in label_lower for indicator in encryption_indicators)
    
    def generate_system_prompt(self) -> str:
        """
        Generate a comprehensive system description for AI threat modelling
        
        Returns:
            Formatted system description string
        """
        prompt_parts = []
        
        # System overview
        prompt_parts.append("# System Architecture Overview")
        prompt_parts.append(f"The system consists of {len(self.elements)} components ")
        prompt_parts.append(f"with {len(self.data_flows)} data flows between them.\n")
        
        # Trust boundaries
        if self.trust_boundaries:
            prompt_parts.append("## Trust Boundaries")
            for boundary in self.trust_boundaries:
                prompt_parts.append(f"- {boundary}")
            prompt_parts.append("")
        
        # Components
        prompt_parts.append("## System Components\n")
        
        for element in self.elements:
            prompt_parts.append(f"### {element.name}")
            prompt_parts.append(f"- Type: {element.element_type}")
            prompt_parts.append(f"- Trust Level: {element.trust_level}")
            
            if element.technologies:
                prompt_parts.append(f"- Technologies: {', '.join(element.technologies)}")
            
            # Find connected flows
            inbound = [f for f in self.data_flows if f.target_id == element.id]
            outbound = [f for f in self.data_flows if f.source_id == element.id]
            
            if inbound:
                prompt_parts.append(f"- Inbound connections: {len(inbound)}")
            if outbound:
                prompt_parts.append(f"- Outbound connections: {len(outbound)}")
            
            prompt_parts.append("")
        
        # Data flows
        prompt_parts.append("## Data Flows\n")
        
        for flow in self.data_flows:
            source = self._get_element_name(flow.source_id)
            target = self._get_element_name(flow.target_id)
            
            flow_desc = f"- {source} → {target}"
            if flow.label:
                flow_desc += f": {flow.label}"
            if flow.protocol != 'unknown':
                flow_desc += f" ({flow.protocol})"
            if flow.encrypted:
                flow_desc += " [Encrypted]"
            
            prompt_parts.append(flow_desc)
        
        return "\n".join(prompt_parts)
    
    def _get_element_name(self, element_id: str) -> str:
        """Get element name by ID"""
        for element in self.elements:
            if element.id == element_id:
                return element.name
        return f"Unknown_{element_id}"
    
    def get_stride_analysis_hints(self) -> Dict[str, List[str]]:
        """
        Generate STRIDE-specific analysis hints based on diagram
        
        Returns:
            Dictionary of STRIDE categories with specific hints
        """
        hints = {
            'Spoofing': [],
            'Tampering': [],
            'Repudiation': [],
            'Information Disclosure': [],
            'Denial of Service': [],
            'Elevation of Privilege': []
        }
        
        # Analyze for spoofing risks
        external_entities = [e for e in self.elements if e.element_type == 'external_entity']
        if external_entities:
            hints['Spoofing'].append(
                f"External entities detected: {', '.join([e.name for e in external_entities])}. "
                "Consider authentication mechanisms."
            )
        
        # Analyze for tampering risks
        unencrypted_flows = [f for f in self.data_flows if not f.encrypted]
        if unencrypted_flows:
            hints['Tampering'].append(
                f"{len(unencrypted_flows)} unencrypted data flows detected. "
                "Consider implementing encryption."
            )
        
        # Analyze for information disclosure
        data_stores = [e for e in self.elements if e.element_type == 'data_store']
        if data_stores:
            hints['Information Disclosure'].append(
                f"{len(data_stores)} data stores found. "
                "Ensure proper access controls and encryption at rest."
            )
        
        # Analyze for DoS
        if len(self.data_flows) > 5:
            hints['Denial of Service'].append(
                "Multiple data flows detected. Consider rate limiting and input validation."
            )
        
        # Analyze for elevation of privilege
        trust_levels = set([e.trust_level for e in self.elements])
        if len(trust_levels) > 1:
            hints['Elevation of Privilege'].append(
                "Multiple trust levels detected. Ensure proper boundary enforcement."
            )
        
        # Remove empty categories
        return {k: v for k, v in hints.items() if v}
    
    def export_to_json(self) -> str:
        """Export parsed diagram data to JSON"""
        data = {
            'elements': [asdict(e) for e in self.elements],
            'data_flows': [asdict(f) for f in self.data_flows],
            'trust_boundaries': self.trust_boundaries,
            'statistics': {
                'total_elements': len(self.elements),
                'total_flows': len(self.data_flows),
                'element_types': self._count_element_types(),
            }
        }
        return json.dumps(data, indent=2)
    
    def _count_element_types(self) -> Dict[str, int]:
        """Count elements by type"""
        counts = {}
        for element in self.elements:
            counts[element.element_type] = counts.get(element.element_type, 0) + 1
        return counts


def integrate_diagram_with_ai(
    diagram_xml: str,
    framework: str = "STRIDE",
    compliance_requirements: List[str] = None
) -> Dict[str, Any]:
    """
    Main integration function: analyze diagram and prepare for AI threat modelling
    
    Args:
        diagram_xml: Raw XML from draw.io
        framework: Threat modelling framework (STRIDE, PASTA, etc.)
        compliance_requirements: List of compliance frameworks to consider
        
    Returns:
        Dictionary containing system prompt and analysis hints
    """
    analyzer = DiagramThreatAnalyzer()
    
    if not analyzer.parse_diagram_xml(diagram_xml):
        return {
            'success': False,
            'error': 'Failed to parse diagram'
        }
    
    # Generate comprehensive system description
    system_description = analyzer.generate_system_prompt()
    
    # Get framework-specific hints
    stride_hints = analyzer.get_stride_analysis_hints() if framework == "STRIDE" else {}
    
    # Build the prompt for AI
    ai_prompt_parts = [system_description]
    
    if compliance_requirements:
        ai_prompt_parts.append("\n## Compliance Requirements")
        for req in compliance_requirements:
            ai_prompt_parts.append(f"- {req}")
    
    if stride_hints:
        ai_prompt_parts.append("\n## Initial Risk Indicators")
        for category, hints in stride_hints.items():
            ai_prompt_parts.append(f"\n### {category}")
            for hint in hints:
                ai_prompt_parts.append(f"- {hint}")
    
    return {
        'success': True,
        'system_description': system_description,
        'ai_prompt': "\n".join(ai_prompt_parts),
        'analysis_hints': stride_hints,
        'diagram_json': analyzer.export_to_json(),
        'statistics': {
            'elements': len(analyzer.elements),
            'flows': len(analyzer.data_flows),
            'boundaries': len(analyzer.trust_boundaries)
        }
    }


if __name__ == "__main__":
    # Example usage
    example_xml = """
    <?xml version="1.0" encoding="UTF-8"?>
    <mxfile>
        <diagram>
            <mxGraphModel>
                <root>
                    <mxCell id="0"/>
                    <mxCell id="1" parent="0"/>
                    <mxCell id="2" value="Web App" style="ellipse" vertex="1" parent="1"/>
                    <mxCell id="3" value="Database" style="cylinder" vertex="1" parent="1"/>
                    <mxCell id="4" value="" edge="1" source="2" target="3" parent="1">
                        <mxGeometry relative="1"/>
                    </mxCell>
                </root>
            </mxGraphModel>
        </diagram>
    </mxfile>
    """
    
    result = integrate_diagram_with_ai(example_xml)
    print(json.dumps(result, indent=2))
