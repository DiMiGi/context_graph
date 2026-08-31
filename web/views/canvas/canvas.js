// Módulo Canvas / ForceGraph
export const TYPE_COLORS = {
  "Schema": "#ec4899",
  "Class": "#8b5cf6",
  "Function": "#10b981",
  "Module": "#3b82f6",
  "Concept": "#f59e0b",
  "Document": "#64748b",
  "Config": "#06b6d4",
  "Asset": "#94a3b8"
};

let graph = null;
let selectedNode = null;
let isSimulationPaused = false;
let currentProjectId = "";

export function initCanvas(containerId, onNodeSelected, onNodeDeleted) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const width = container.clientWidth || window.innerWidth;
  const height = container.clientHeight || (window.innerHeight - 56);

  graph = ForceGraph()(container)
    .width(width)
    .height(height)
    .backgroundColor('#0a0e14')
    .nodeId('id')
    .nodeLabel(n => `${n.type}: ${n.label}\n${n.path || ''}`)
    .nodeColor(n => TYPE_COLORS[n.type] || '#00e5ff')
    .linkColor(() => '#38bdf8')
    .linkWidth(1.8)
    .linkDirectionalArrowLength(5)
    .linkDirectionalArrowRelPos(0.95)
    .linkCurvature(0.08)
    .d3AlphaDecay(0.02)
    .d3VelocityDecay(0.3)
    .minZoom(0.05)
    .maxZoom(12.0)
    .enableNodeDrag(true)
    .enableZoomInteraction(true)
    .enablePanInteraction(true)
    .onNodeClick(node => {
      openInspector(node);
      graph.centerAt(node.x, node.y, 400);
      graph.zoom(3.0, 400);
      if (onNodeSelected) onNodeSelected(node);
    })
    .onBackgroundClick(() => closeInspector())
    .cooldownTicks(120);

  // Renderizado optimizado con Level of Detail (LOD)
  graph.nodeCanvasObject((node, ctx, globalScale) => {
    const label = node.label || node.id;
    const baseRadius = node.type === "Schema" ? 7 : (node.type === "Class" ? 5.5 : (node.type === "Module" ? 4.5 : 3.5));
    const radius = globalScale < 0.6 ? baseRadius * (0.4 + 0.6 * globalScale) : baseRadius;

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = TYPE_COLORS[node.type] || '#00e5ff';
    ctx.fill();
    ctx.lineWidth = 1.0 / globalScale;
    ctx.strokeStyle = node === selectedNode ? '#ffffff' : (node.is_custom ? '#f59e0b' : '#0f172a');
    ctx.stroke();

    if (globalScale > 1.1 || node === selectedNode) {
      const fontSize = Math.max(10 / globalScale, 2.5);
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = '#f8fafc';
      ctx.fillText(label, node.x, node.y + radius + (2 / globalScale));
    }
  });

  graph.nodePointerAreaPaint((node, color, ctx) => {
    const baseRadius = (node.type === "Schema" ? 7 : (node.type === "Class" ? 5.5 : (node.type === "Module" ? 4.5 : 3.5))) + 3;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, baseRadius, 0, 2 * Math.PI, false);
    ctx.fill();
  });

  // Botones overlay de control
  document.getElementById('btn-fit')?.addEventListener('click', () => graph?.zoomToFit(400, 30));
  document.getElementById('btn-pause-sim')?.addEventListener('click', () => {
    isSimulationPaused = !isSimulationPaused;
    const currentNodes = graph?.graphData()?.nodes || [];
    const btn = document.getElementById('btn-pause-sim');
    if (isSimulationPaused) {
      currentNodes.forEach(n => { n.fx = n.x; n.fy = n.y; });
      graph.cooldownTicks(0);
      if (btn) btn.textContent = '▶️ Reanudar';
    } else {
      currentNodes.forEach(n => { n.fx = undefined; n.fy = undefined; });
      graph.cooldownTicks(120);
      graph.d3ReheatSimulation();
      if (btn) btn.textContent = '⏸️ Pausar';
    }
  });

  document.getElementById('btn-close-inspector')?.addEventListener('click', closeInspector);

  // Guardar cambios de nodo
  document.getElementById('btn-save-node')?.addEventListener('click', async () => {
    if (!selectedNode || !currentProjectId) return;
    const updateData = {
      label: document.getElementById('node-label').value,
      type: document.getElementById('node-type').value,
      path: document.getElementById('node-path').value,
      description: document.getElementById('node-desc').value
    };
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/graph/nodes/${encodeURIComponent(selectedNode.id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updateData)
      });
      if (res.ok) {
        Object.assign(selectedNode, updateData);
        selectedNode.is_custom = true;
        alert('Nodo actualizado correctamente.');
      }
    } catch (e) {
      alert('Error: ' + e.message);
    }
  });

  // Eliminar nodo
  document.getElementById('btn-delete-node')?.addEventListener('click', async () => {
    if (!selectedNode || !currentProjectId) return;
    if (!confirm(`¿Eliminar nodo ${selectedNode.id}?`)) return;
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/graph/nodes/${encodeURIComponent(selectedNode.id)}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        closeInspector();
        if (onNodeDeleted) onNodeDeleted(selectedNode.id);
      }
    } catch (e) {
      alert('Error: ' + e.message);
    }
  });

  window.addEventListener('resize', () => {
    if (graph && container) {
      const rect = container.getBoundingClientRect();
      graph.width(rect.width);
      graph.height(rect.height);
    }
  });

  return graph;
}

export function setGraphData(projectId, nodes, edges) {
  currentProjectId = projectId;
  if (!graph) return;

  const nodeIds = new Set(nodes.map(n => n.id));
  const links = edges
    .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map(e => ({
      source: e.source,
      target: e.target,
      relation: e.relation
    }));

  graph.graphData({ nodes: [...nodes], links });
  setTimeout(() => graph.zoomToFit(400, 50), 150);
}

export function filterGraph(type, searchQuery, rawNodes, rawEdges) {
  if (!graph || !rawNodes) return;
  const q = (searchQuery || "").toLowerCase().trim();

  let filtered = rawNodes;
  if (type && type !== "ALL") {
    filtered = filtered.filter(n => n.type === type);
  }
  if (q) {
    filtered = filtered.filter(n =>
      (n.label && n.label.toLowerCase().includes(q)) ||
      (n.id && n.id.toLowerCase().includes(q)) ||
      (n.path && n.path.toLowerCase().includes(q))
    );
  }

  const nodeIds = new Set(filtered.map(n => n.id));
  const filteredLinks = rawEdges
    .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map(e => ({ source: e.source, target: e.target, relation: e.relation }));

  graph.graphData({ nodes: [...filtered], links: filteredLinks });
}

export function openInspector(node) {
  selectedNode = node;
  const drawer = document.getElementById('inspector-drawer');
  if (!drawer) return;

  document.getElementById('node-id').value = node.id || '';
  document.getElementById('node-label').value = node.label || '';
  document.getElementById('node-type').value = node.type || 'Concept';
  document.getElementById('node-path').value = node.path || '';
  document.getElementById('node-desc').value = node.description || '';
  drawer.classList.remove('hidden');
}

export function closeInspector() {
  selectedNode = null;
  document.getElementById('inspector-drawer')?.classList.add('hidden');
}
