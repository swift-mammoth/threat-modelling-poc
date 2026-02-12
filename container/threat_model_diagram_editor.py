"""
Threat Model Diagram Editor — self-contained mxGraph editor.
mxClient.min.js is read at import time and inlined directly into the HTML
so there are zero external requests, no fetch(), no dynamic script tags.
"""

import os
import streamlit as st
import streamlit.components.v1 as components
from typing import Optional, Dict, Any
import xml.etree.ElementTree as ET

# Read mxGraph once at module load time from the static directory next to app.py
_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
_MXGRAPH_JS_PATH = os.path.join(_STATIC_DIR, "mxClient.min.js")

try:
    with open(_MXGRAPH_JS_PATH, "r", encoding="utf-8") as _f:
        _MXGRAPH_JS = _f.read()
    # Escape any </script sequences so they don't close our inline <script> block
    # when the HTML parser scans the page before JS execution.
    import re as _re
    _MXGRAPH_JS = _re.sub(r'(?i)</script', r'<\/script', _MXGRAPH_JS)
    _MXGRAPH_AVAILABLE = True
except FileNotFoundError:
    _MXGRAPH_JS = ""
    _MXGRAPH_AVAILABLE = False


def _build_editor_html(height: int, initial_xml: str) -> str:
    """Return a fully self-contained HTML page with mxGraph inlined."""

    # Escape the initial XML for safe embedding inside a JS template literal
    safe_xml = (
        initial_xml
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("</script>", "<\\/script>")
    )

    if not _MXGRAPH_AVAILABLE:
        return f"""<!DOCTYPE html><html><body style="font-family:Arial;padding:20px;">
<p style="color:#c00;">&#10060; mxClient.min.js not found at {_MXGRAPH_JS_PATH}</p>
<p>Ensure <code>container/static/mxClient.min.js</code> is present and the Dockerfile copies <code>static/</code>.</p>
</body></html>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:{height}px;overflow:hidden;font-family:Arial,sans-serif;background:#fff}}
#toolbar{{display:flex;align-items:center;gap:5px;padding:5px 8px;background:#f5f5f5;
  border-bottom:1px solid #ddd;height:40px;min-height:40px;flex-wrap:wrap}}
.btn{{padding:3px 9px;font-size:12px;cursor:pointer;border:1px solid #ccc;
  border-radius:3px;background:#fff;white-space:nowrap}}
.btn:hover{{background:#e8e8e8}}
.btn.primary{{background:#1a73e8;color:#fff;border-color:#1a73e8}}
.btn.primary:hover{{background:#1558b0}}
.sep{{width:1px;height:22px;background:#ddd;margin:0 2px}}
#status{{font-size:11px;color:#666;margin-left:auto;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
#main{{display:flex;height:calc({height}px - 40px)}}
#sidebar{{width:125px;min-width:125px;border-right:1px solid #ddd;overflow-y:auto;
  padding:5px;background:#fafafa}}
.sg{{margin-bottom:8px}}
.sg h4{{font-size:10px;color:#666;margin-bottom:3px;text-transform:uppercase;letter-spacing:.4px}}
.si{{display:flex;align-items:center;gap:4px;padding:3px 5px;margin-bottom:2px;
  cursor:grab;border:1px solid #e0e0e0;border-radius:3px;background:#fff;
  font-size:11px;user-select:none}}
.si:hover{{background:#e8f0fe;border-color:#1a73e8}}
.si em{{font-size:13px;width:16px;text-align:center;flex-shrink:0;font-style:normal}}
#canvas-wrap{{flex:1;overflow:hidden;position:relative;background:#fff}}
#mx-container{{width:100%;height:100%;overflow:hidden}}
#overlay{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
  font-size:13px;color:#888;text-align:center;pointer-events:none}}
</style>
</head>
<body>

<div id="toolbar">
  <button class="btn" onclick="addShape('process')">&#9711; Process</button>
  <button class="btn" onclick="addShape('store')">&#9645; Store</button>
  <button class="btn" onclick="addShape('entity')">&#9633; Entity</button>
  <button class="btn" onclick="addShape('boundary')">&#9643; Boundary</button>
  <div class="sep"></div>
  <button class="btn" onclick="deleteSelected()">&#128465;</button>
  <button class="btn" onclick="undoLast()">&#8617;</button>
  <button class="btn" onclick="zoomIn()">&#xFF0B;</button>
  <button class="btn" onclick="zoomOut()">&#xFF0D;</button>
  <button class="btn" onclick="fitPage()">&#8861; Fit</button>
  <div class="sep"></div>
  <button class="btn primary" onclick="exportXml()">&#128190; Save XML</button>
  <span id="status">Initialising...</span>
</div>

<div id="main">
  <div id="sidebar">
    <div class="sg"><h4>DFD</h4>
      <div class="si" draggable="true" data-shape="process" ondragstart="drag(event)"><em>&#9711;</em>Process</div>
      <div class="si" draggable="true" data-shape="store"   ondragstart="drag(event)"><em>&#9645;</em>Data Store</div>
      <div class="si" draggable="true" data-shape="entity"  ondragstart="drag(event)"><em>&#9633;</em>Ext Entity</div>
      <div class="si" draggable="true" data-shape="boundary" ondragstart="drag(event)"><em>&#9643;</em>Boundary</div>
    </div>
    <div class="sg"><h4>Components</h4>
      <div class="si" draggable="true" data-shape="actor"  ondragstart="drag(event)"><em>&#128100;</em>Actor</div>
      <div class="si" draggable="true" data-shape="cloud"  ondragstart="drag(event)"><em>&#9729;</em>Cloud</div>
      <div class="si" draggable="true" data-shape="api"    ondragstart="drag(event)"><em>&#9881;</em>API</div>
      <div class="si" draggable="true" data-shape="db"     ondragstart="drag(event)"><em>&#128190;</em>Database</div>
    </div>
  </div>

  <div id="canvas-wrap" ondragover="event.preventDefault()" ondrop="dropShape(event)">
    <div id="mx-container"></div>
    <div id="overlay">Initialising editor...</div>
  </div>
</div>

<script>
// ── mxGraph inlined ──────────────────────────────────────────────────────────
window.mxBasePath        = '';
window.mxImageBasePath   = '';
window.mxLoadResources   = false;
window.mxLoadStylesheets = false;
window.mxForceIncludes   = false;
{_MXGRAPH_JS}
// ── Editor code ─────────────────────────────────────────────────────────────

var graph=null, model=null, undoMgr=null, dragShape=null, px=80, py=80;

var S={{
  process :'ellipse;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=11;',
  store   :'rounded=0;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=11;arcSize=50;',
  entity  :'rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=11;',
  boundary:'rounded=1;dashed=1;dashPattern=8 4;fillColor=none;strokeColor=#d00;strokeWidth=2;fontSize=11;opacity=20;verticalLabelPosition=bottom;',
  actor   :'rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;fontSize=11;',
  cloud   :'ellipse;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=11;',
  api     :'rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=11;',
  db      :'rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=11;arcSize=50;'
}};
var SZ={{process:[120,60],store:[130,50],entity:[100,50],boundary:[220,160],
         actor:[80,50],cloud:[100,60],api:[80,50],db:[100,50]}};

function st2(m){{document.getElementById('status').textContent=m;}}

function init(){{
  try{{
    mxEvent.disableContextMenu(document.body);
    var c=document.getElementById('mx-container');
    document.getElementById('overlay').style.display='none';

    graph=new mxGraph(c); model=graph.getModel();
    graph.setConnectable(true); graph.setEnabled(true); graph.setPanning(true);
    graph.setHtmlLabels(true); graph.setCellsEditable(true);
    graph.setGridEnabled(true); graph.setGridSize(10);
    graph.setAllowDanglingEdges(false);
    graph.panningHandler.useRightButtonForPanning=true;

    var es=graph.getStylesheet().getDefaultEdgeStyle();
    es[mxConstants.STYLE_ROUNDED]=true;
    es[mxConstants.STYLE_EDGE]=mxEdgeStyle.ElbowConnector;

    new mxRubberband(graph);

    undoMgr=new mxUndoManager();
    graph.getModel().addListener(mxEvent.CHANGE,function(s,e){{
      undoMgr.undoableEditHappened(e.getProperty('edit'));
    }});

    var kh=new mxKeyHandler(graph);
    kh.bindKey(46,deleteSelected); kh.bindKey(8,deleteSelected);

    var xml=`{safe_xml}`;
    if(xml&&xml.trim()){{
      try{{
        var doc=mxUtils.parseXml(xml);
        new mxCodec(doc).decode(doc.documentElement,model);
        setTimeout(function(){{graph.fit();}},100);
      }}catch(e){{console.warn('XML parse:',e);}}
    }}

    st2('Ready — drag shapes or click toolbar');
  }}catch(e){{
    document.getElementById('overlay').innerHTML='&#10060; '+e.message;
    document.getElementById('overlay').style.display='block';
    st2('Error: '+e.message);
    console.error(e);
  }}
}}

// Run immediately — mxGraph is already defined above
init();

function addShape(t){{
  if(!graph)return;
  var sz=SZ[t]||[100,50];
  model.beginUpdate();
  try{{
    var v=graph.insertVertex(graph.getDefaultParent(),null,
      t.charAt(0).toUpperCase()+t.slice(1),px,py,sz[0],sz[1],S[t]);
    px+=20; py+=20; if(px>400){{px=80;py=80;}}
    graph.setSelectionCell(v);
  }}finally{{model.endUpdate();}}
}}
function deleteSelected(){{if(graph)graph.removeCells(graph.getSelectionCells());}}
function undoLast(){{if(undoMgr)undoMgr.undo();}}
function zoomIn(){{if(graph)graph.zoomIn();}}
function zoomOut(){{if(graph)graph.zoomOut();}}
function fitPage(){{if(graph)graph.fit();}}

function exportXml(){{
  if(!graph)return;
  var xml=mxUtils.getXml(new mxCodec(mxUtils.createXmlDocument()).encode(graph.getModel()));
  sessionStorage.setItem('drawio_xml',xml);

  // Push XML into the Streamlit text_area with data-testid="diagram-xml-bridge"
  // so Python can read it via session_state without any file upload.
  try{{
    var ta=window.parent.document.querySelector('textarea[data-testid="diagram-xml-bridge"]');
    if(!ta){{
      // Fallback: find by placeholder text
      ta=window.parent.document.querySelector('textarea[placeholder="diagram-xml-bridge"]');
    }}
    if(ta){{
      // Set value and fire React synthetic change event
      var nativeInputValueSetter=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
      nativeInputValueSetter.call(ta,xml);
      ta.dispatchEvent(new Event('input',{{bubbles:true}}));
      st2('\u2705 Diagram saved — click Analyse tab');
    }}else{{
      // Textarea not found in parent - copy to clipboard as fallback
      if(navigator.clipboard&&navigator.clipboard.writeText){{
        navigator.clipboard.writeText(xml).then(function(){{
          st2('XML copied to clipboard — paste into the XML box below');
        }}).catch(function(){{showBox(xml);}});
      }}else{{showBox(xml);}}
    }}
  }}catch(e){{
    // Cross-origin or other error - fall back to showBox
    showBox(xml);
    st2('Copy the XML and paste into the XML box below');
  }}
}}
function showBox(xml){{
  var ta=document.createElement('textarea');
  ta.value=xml;
  ta.style.cssText='position:fixed;top:0;left:0;right:0;bottom:36px;z-index:9999;font-size:11px;font-family:monospace;padding:8px;border:none;';
  var btn=document.createElement('button');
  btn.textContent='Close';
  btn.style.cssText='position:fixed;bottom:0;left:0;right:0;height:36px;z-index:10000;font-size:14px;background:#1a73e8;color:#fff;border:none;cursor:pointer;';
  btn.onclick=function(){{document.body.removeChild(ta);document.body.removeChild(btn);}};
  document.body.appendChild(ta); document.body.appendChild(btn); ta.select();
}}

function drag(evt){{dragShape=(evt.target.dataset.shape||evt.currentTarget.dataset.shape);evt.dataTransfer.setData('text/plain',dragShape);}}
function dropShape(evt){{
  evt.preventDefault(); if(!graph||!dragShape)return;
  var r=document.getElementById('canvas-wrap').getBoundingClientRect();
  var tr=graph.view.translate,sc=graph.view.scale;
  var gx=((evt.clientX-r.left)/sc)-tr.x, gy=((evt.clientY-r.top)/sc)-tr.y;
  var sz=SZ[dragShape]||[100,50];
  model.beginUpdate();
  try{{graph.insertVertex(graph.getDefaultParent(),null,
    dragShape.charAt(0).toUpperCase()+dragShape.slice(1),
    gx-sz[0]/2,gy-sz[1]/2,sz[0],sz[1],S[dragShape]);}}
  finally{{model.endUpdate();}}
  dragShape=null;
}}
</script>
</body>
</html>"""


class DiagramEditor:
    @staticmethod
    def render_editor(height: int = 800, initial_diagram: Optional[str] = None, key: str = "diagram_editor") -> str:
        empty = "<mxGraphModel><root><mxCell id='0'/><mxCell id='1' parent='0'/></root></mxGraphModel>"
        return _build_editor_html(height, initial_diagram or empty)

    @staticmethod
    def extract_threat_model_elements(diagram_xml: str) -> Dict[str, Any]:
        try:
            root = ET.fromstring(diagram_xml)
            elements = {"processes":[],"data_stores":[],"external_entities":[],"data_flows":[],"trust_boundaries":[]}
            for cell in root.iter('mxCell'):
                v, s = cell.get('value',''), cell.get('style','')
                if 'ellipse' in s or 'process' in v.lower():
                    elements["processes"].append({"id":cell.get('id'),"name":v,"style":s})
                elif 'arcSize=50' in s or 'store' in v.lower():
                    elements["data_stores"].append({"id":cell.get('id'),"name":v,"style":s})
                elif any(k in v.lower() for k in ['entity','actor','external','user']):
                    elements["external_entities"].append({"id":cell.get('id'),"name":v,"style":s})
                elif cell.get('edge')=='1':
                    elements["data_flows"].append({"id":cell.get('id'),"label":v,"source":cell.get('source'),"target":cell.get('target')})
                elif 'dashed' in s or 'boundary' in v.lower():
                    elements["trust_boundaries"].append({"id":cell.get('id'),"name":v})
            return elements
        except Exception as e:
            st.error(f"Error parsing diagram: {e}")
            return {}


def simple_drawio_embed(height: int = 800) -> None:
    empty = "<mxGraphModel><root><mxCell id='0'/><mxCell id='1' parent='0'/></root></mxGraphModel>"
    components.html(_build_editor_html(height, empty), height=height + 10, scrolling=False)
