"""
Threat Model Diagram Editor Component
Self-hosted mxGraph editor — no external iframe dependencies.
mxClient.min.js is served from /app/static/ (same origin as the Streamlit app).
"""

import streamlit as st
import streamlit.components.v1 as components
from typing import Optional, Dict, Any
import xml.etree.ElementTree as ET


def _mxgraph_editor_html(height: int, initial_xml: str) -> str:
    safe_xml = initial_xml.replace("\\", "\\\\").replace("`", "\\`").replace("</", "<\\/")
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; overflow: hidden; font-family: Arial, sans-serif; background: #fff; }
#toolbar {
  display: flex; align-items: center; gap: 6px; padding: 6px 10px;
  background: #f5f5f5; border-bottom: 1px solid #ddd;
  height: 44px; min-height: 44px; flex-wrap: wrap;
}
.btn {
  padding: 4px 10px; font-size: 12px; cursor: pointer;
  border: 1px solid #ccc; border-radius: 3px; background: #fff; white-space: nowrap;
}
.btn:hover { background: #e8e8e8; }
.btn.primary { background: #1a73e8; color: #fff; border-color: #1a73e8; }
.btn.primary:hover { background: #1558b0; }
.sep { width: 1px; height: 24px; background: #ddd; margin: 0 2px; }
#status { font-size: 11px; color: #888; margin-left: auto; }
#main { display: flex; height: calc(100% - 44px); }
#sidebar {
  width: 130px; min-width: 130px; border-right: 1px solid #ddd;
  overflow-y: auto; padding: 6px; background: #fafafa;
}
.sg { margin-bottom: 8px; }
.sg h4 { font-size: 10px; color: #666; margin-bottom: 3px; text-transform: uppercase; }
.si {
  display: flex; align-items: center; gap: 4px; padding: 3px 5px; margin-bottom: 2px;
  cursor: grab; border: 1px solid #e0e0e0; border-radius: 3px; background: #fff;
  font-size: 11px; user-select: none;
}
.si:hover { background: #e8f0fe; border-color: #1a73e8; }
.si span { font-size: 14px; width: 18px; text-align: center; flex-shrink: 0; }
#canvas-wrap { flex: 1; overflow: hidden; position: relative; }
#mx-container { width: 100%; height: 100%; overflow: hidden; background: #fff; }
#overlay {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
  font-size: 14px; color: #888;
}
</style>
</head>
<body>
<div id="toolbar">
  <button class="btn" onclick="addShape('process')">&#9135; Process</button>
  <button class="btn" onclick="addShape('store')">&#128451; Data Store</button>
  <button class="btn" onclick="addShape('entity')">&#128100; Entity</button>
  <button class="btn" onclick="addShape('boundary')">&#9633; Boundary</button>
  <div class="sep"></div>
  <button class="btn" onclick="deleteSelected()">&#128465; Delete</button>
  <button class="btn" onclick="undoLast()">&#8617; Undo</button>
  <button class="btn" onclick="zoomIn()">&#xFF0B;</button>
  <button class="btn" onclick="zoomOut()">&#xFF0D;</button>
  <button class="btn" onclick="fitPage()">&#8861; Fit</button>
  <div class="sep"></div>
  <button class="btn primary" onclick="exportXml()">&#128190; Save XML</button>
  <span id="status">Loading editor...</span>
</div>
<div id="main">
  <div id="sidebar">
    <div class="sg">
      <h4>DFD Shapes</h4>
      <div class="si" draggable="true" data-shape="process" ondragstart="drag(event)"><span>&#9711;</span> Process</div>
      <div class="si" draggable="true" data-shape="store" ondragstart="drag(event)"><span>&#9645;</span> Data Store</div>
      <div class="si" draggable="true" data-shape="entity" ondragstart="drag(event)"><span>&#9633;</span> Ext Entity</div>
      <div class="si" draggable="true" data-shape="boundary" ondragstart="drag(event)"><span>&#9643;</span> Boundary</div>
    </div>
    <div class="sg">
      <h4>Components</h4>
      <div class="si" draggable="true" data-shape="actor" ondragstart="drag(event)"><span>&#128100;</span> Actor</div>
      <div class="si" draggable="true" data-shape="cloud" ondragstart="drag(event)"><span>&#9729;</span> Cloud</div>
      <div class="si" draggable="true" data-shape="api" ondragstart="drag(event)"><span>&#9881;</span> API</div>
      <div class="si" draggable="true" data-shape="db" ondragstart="drag(event)"><span>&#128190;</span> Database</div>
    </div>
  </div>
  <div id="canvas-wrap" ondragover="event.preventDefault()" ondrop="dropShape(event)">
    <div id="mx-container">
      <div id="overlay">Loading mxGraph...</div>
    </div>
  </div>
</div>
<script>
var graph=null,model=null,undoMgr=null,dragShape=null,placeX=80,placeY=80;
var STYLES={
  process:'ellipse;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=11;',
  store:'rounded=0;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=11;arcSize=50;',
  entity:'rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=11;',
  boundary:'rounded=1;dashed=1;dashPattern=8 4;fillColor=none;strokeColor=#d00;strokeWidth=2;fontSize=11;opacity=20;verticalLabelPosition=bottom;',
  actor:'rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;fontSize=11;',
  cloud:'ellipse;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=11;',
  api:'rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=11;',
  db:'rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=11;arcSize=50;'
};
var SIZES={process:[120,60],store:[130,50],entity:[100,50],boundary:[220,160],actor:[80,50],cloud:[100,60],api:[80,50],db:[100,50]};
function status(m){document.getElementById('status').textContent=m;}
function initGraph(){
  try{
    mxEvent.disableContextMenu(document.body);
    var c=document.getElementById('mx-container');
    document.getElementById('overlay').style.display='none';
    graph=new mxGraph(c); model=graph.getModel();
    graph.setConnectable(true); graph.setEnabled(true); graph.setPanning(true);
    graph.setHtmlLabels(true); graph.setCellsEditable(true); graph.setGridEnabled(true);
    graph.setGridSize(10); graph.setAllowDanglingEdges(false);
    graph.panningHandler.useRightButtonForPanning=true;
    var es=graph.getStylesheet().getDefaultEdgeStyle();
    es[mxConstants.STYLE_ROUNDED]=true;
    es[mxConstants.STYLE_EDGE]=mxEdgeStyle.ElbowConnector;
    new mxRubberband(graph);
    undoMgr=new mxUndoManager();
    graph.getModel().addListener(mxEvent.CHANGE,function(s,e){undoMgr.undoableEditHappened(e.getProperty('edit'));});
    var kh=new mxKeyHandler(graph);
    kh.bindKey(46,deleteSelected); kh.bindKey(8,deleteSelected);
    var xml=`""" + safe_xml + """`;
    if(xml&&xml.trim()){try{var doc=mxUtils.parseXml(xml);var codec=new mxCodec(doc);codec.decode(doc.documentElement,model);setTimeout(function(){graph.fit();},100);}catch(e){console.warn('XML load:',e);}}
    status('Ready — drag shapes or use the toolbar');
    return true;
  }catch(e){
    document.getElementById('overlay').innerHTML='Failed: '+e.message;
    document.getElementById('overlay').style.display='block';
    status('Error: '+e.message); return false;
  }
}
(function(){
  var s=document.createElement('script');
  s.src='/app/static/mxClient.min.js';
  s.onload=function(){status('Library loaded...');setTimeout(initGraph,50);};
  s.onerror=function(){
    document.getElementById('overlay').innerHTML='Could not load /app/static/mxClient.min.js';
    document.getElementById('overlay').style.display='block';
    status('Library load failed');
  };
  document.head.appendChild(s);
})();
function addShape(t){
  if(!graph)return;
  var sz=SIZES[t]||[100,50];
  model.beginUpdate();
  try{var v=graph.insertVertex(graph.getDefaultParent(),null,t.charAt(0).toUpperCase()+t.slice(1),placeX,placeY,sz[0],sz[1],STYLES[t]);placeX+=20;placeY+=20;if(placeX>400){placeX=80;placeY=80;}graph.setSelectionCell(v);}
  finally{model.endUpdate();}
}
function deleteSelected(){if(graph)graph.removeCells(graph.getSelectionCells());}
function undoLast(){if(undoMgr)undoMgr.undo();}
function zoomIn(){if(graph)graph.zoomIn();}
function zoomOut(){if(graph)graph.zoomOut();}
function fitPage(){if(graph)graph.fit();}
function exportXml(){
  if(!graph)return;
  var enc=new mxCodec(mxUtils.createXmlDocument());
  var node=enc.encode(graph.getModel());
  var xml=mxUtils.getXml(node);
  sessionStorage.setItem('drawio_xml',xml);
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(xml).then(function(){status('XML copied to clipboard — paste into .xml file and upload below');}).catch(function(){showBox(xml);});
  }else{showBox(xml);}
}
function showBox(xml){
  var ta=document.createElement('textarea');
  ta.value=xml;ta.style.cssText='position:fixed;top:0;left:0;right:0;bottom:40px;z-index:9999;font-size:11px;font-family:monospace;padding:8px;';
  var btn=document.createElement('button');btn.textContent='Close';
  btn.style.cssText='position:fixed;bottom:0;left:0;right:0;height:36px;z-index:10000;font-size:14px;background:#1a73e8;color:#fff;border:none;cursor:pointer;';
  btn.onclick=function(){document.body.removeChild(ta);document.body.removeChild(btn);};
  document.body.appendChild(ta);document.body.appendChild(btn);ta.select();
}
function drag(evt){dragShape=(evt.target.dataset.shape||evt.currentTarget.dataset.shape);evt.dataTransfer.setData('text/plain',dragShape);}
function dropShape(evt){
  evt.preventDefault();if(!graph||!dragShape)return;
  var rect=document.getElementById('canvas-wrap').getBoundingClientRect();
  var x=evt.clientX-rect.left,y=evt.clientY-rect.top;
  var tr=graph.view.translate,sc=graph.view.scale;
  var gx=(x/sc)-tr.x,gy=(y/sc)-tr.y;
  var sz=SIZES[dragShape]||[100,50];
  model.beginUpdate();
  try{graph.insertVertex(graph.getDefaultParent(),null,dragShape.charAt(0).toUpperCase()+dragShape.slice(1),gx-sz[0]/2,gy-sz[1]/2,sz[0],sz[1],STYLES[dragShape]);}
  finally{model.endUpdate();}
  dragShape=null;
}
</script>
</body>
</html>"""


class DiagramEditor:
    @staticmethod
    def render_editor(height: int = 800, initial_diagram: Optional[str] = None, key: str = "diagram_editor") -> str:
        empty = "<mxGraphModel><root><mxCell id='0'/><mxCell id='1' parent='0'/></root></mxGraphModel>"
        return _mxgraph_editor_html(height, initial_diagram or empty)

    @staticmethod
    def extract_threat_model_elements(diagram_xml: str) -> Dict[str, Any]:
        try:
            root = ET.fromstring(diagram_xml)
            elements = {"processes": [], "data_stores": [], "external_entities": [], "data_flows": [], "trust_boundaries": []}
            for cell in root.iter('mxCell'):
                value = cell.get('value', '')
                style = cell.get('style', '')
                if 'ellipse' in style or 'process' in value.lower():
                    elements["processes"].append({"id": cell.get('id'), "name": value, "style": style})
                elif 'arcSize=50' in style or 'store' in value.lower():
                    elements["data_stores"].append({"id": cell.get('id'), "name": value, "style": style})
                elif any(k in value.lower() for k in ['entity', 'actor', 'external', 'user']):
                    elements["external_entities"].append({"id": cell.get('id'), "name": value, "style": style})
                elif cell.get('edge') == '1':
                    elements["data_flows"].append({"id": cell.get('id'), "label": value, "source": cell.get('source'), "target": cell.get('target')})
                elif 'dashed' in style or 'boundary' in value.lower():
                    elements["trust_boundaries"].append({"id": cell.get('id'), "name": value})
            return elements
        except Exception as e:
            st.error(f"Error parsing diagram: {str(e)}")
            return {}


def simple_drawio_embed(height: int = 800) -> None:
    empty = "<mxGraphModel><root><mxCell id='0'/><mxCell id='1' parent='0'/></root></mxGraphModel>"
    components.html(_mxgraph_editor_html(height, empty), height=height + 50)
