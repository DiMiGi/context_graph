// Módulo Canvas de Alto Rendimiento con Coordenadas Precalculadas y Cero Física en Navegador
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
let currentProjectId = "";

// Almacén maestro de datos en memoria
let masterNodes = [];
let masterEdges = [];
let masterNodesMap = new Map();

// Conjunto filtrado activo
let activeFilteredNodes = [];
let activeFilteredEdges = [];

export function isCanvasInitialized() {
  return graph !== null;
}

export function pauseCanvas() {
  if (graph) {
    graph.pauseAnimation();
  }
}

export function resumeCanvas() {
  if (graph) {
    graph.resumeAnimation();
    resizeCanvas();
  }
}

export function initCanvas(containerId, onNodeSelected, onNodeDeleted) {
  if (graph) return graph;

  const container = document.getElementById(containerId);
  if (!container) return null;

  container.innerHTML = '';

  const width = container.clientWidth || window.innerWidth;
  const height = container.clientHeight || (window.innerHeight - 56);

  graph = ForceGraph()(container)
    .width(width)
    .height(height)
    .backgroundColor('#0a0e14')
    .nodeId('id')
    .nodeLabel(n => `${n.type}: ${n.label || n.id}\n${n.path || ''}`)
    .nodeColor(n => TYPE_COLORS[n.type] || '#00e5ff')
    .linkColor(() => '#38bdf8')
    .linkWidth(1.2)
    .linkDirectionalArrowLength(4)
    .linkDirectionalArrowRelPos(0.95)
    .linkCurvature(0.06)
    .warmupTicks(0)
    .cooldownTicks(0)
    .d3AlphaDecay(1)
    .d3VelocityDecay(1)
    .minZoom(0.01)
    .maxZoom(20.0)
    .enableNodeDrag(true)
    .onNodeDrag((node) => {
      node.fx = node.x;
      node.fy = node.y;
    })
    .enableZoomInteraction(true)
    .enablePanInteraction(true)
    .onNodeClick(node => {
      if (node) {
        selectedNode = node;
        openInspector(node);
        if (onNodeSelected) onNodeSelected(node);
      }
    })
    .onBackgroundClick(() => closeInspector());

  // Renderizado optimizado con LOD (Level of Detail) para grafos masivos
  graph.nodeCanvasObject((node, ctx, globalScale) => {
    const label = node.label || node.id;
    const baseRadius = node.type === "Schema" ? 7 : (node.type === "Class" ? 5 : (node.type === "Module" ? 4 : 3));
    const radius = globalScale < 0.5 ? baseRadius * (0.3 + 0.7 * globalScale) : baseRadius;

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = TYPE_COLORS[node.type] || '#00e5ff';
    ctx.fill();
    ctx.lineWidth = 1.0 / globalScale;
    ctx.strokeStyle = node === selectedNode ? '#ffffff' : (node.is_custom ? '#f59e0b' : '#0f172a');
    ctx.stroke();

    // Mostrar etiquetas sólo si hay suficiente zoom o está seleccionado
    if (globalScale > 0.85 || node === selectedNode) {
      const fontSize = Math.max(10 / globalScale, 2.5);
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = '#f8fafc';
      ctx.fillText(label, node.x, node.y + radius + (2 / globalScale));
    }
  });

  graph.nodePointerAreaPaint((node, color, ctx) => {
    const baseRadius = (node.type === "Schema" ? 7 : (node.type === "Class" ? 5 : 3.5)) + 4;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, baseRadius, 0, 2 * Math.PI, false);
    ctx.fill();
  });

  // Botón Centrar Vista
  document.getElementById('btn-fit')?.addEventListener('click', () => {
    graph?.zoomToFit(400, 40);
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
        const master = masterNodesMap.get(selectedNode.id);
        if (master) Object.assign(master, updateData, { is_custom: true });
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
        const deletedId = selectedNode.id;
        closeInspector();
        masterNodes = masterNodes.filter(n => n.id !== deletedId);
        masterEdges = masterEdges.filter(e => e.source !== deletedId && e.target !== deletedId);
        masterNodesMap.delete(deletedId);
        activeFilteredNodes = activeFilteredNodes.filter(n => n.id !== deletedId);
        activeFilteredEdges = activeFilteredEdges.filter(e => e.source !== deletedId && e.target !== deletedId);
        renderGraphData();
        if (onNodeDeleted) onNodeDeleted(deletedId);
      }
    } catch (e) {
      alert('Error: ' + e.message);
    }
  });

  window.addEventListener('resize', () => {
    resizeCanvas();
  });

  if (masterNodes.length > 0) {
    renderGraphData();
  }

  return graph;
}

export function resizeCanvas() {
  const container = document.getElementById('graph-canvas-element');
  if (graph && container) {
    const rect = container.getBoundingClientRect();
    const w = rect.width || window.innerWidth;
    const h = rect.height || (window.innerHeight - 56);
    if (w > 0 && h > 0) {
      graph.width(w);
      graph.height(h);
    }
  }
}

// Carga inicial del proyecto en el almacén maestro
export function setGraphData(projectId, nodes, edges) {
  currentProjectId = projectId;

  masterNodes = (nodes || []).map(n => ({
    ...n,
    fx: typeof n.x === 'number' ? n.x : undefined,
    fy: typeof n.y === 'number' ? n.y : undefined
  }));
  masterEdges = (edges || []).map(e => ({ ...e }));

  masterNodesMap.clear();
  masterNodes.forEach(n => masterNodesMap.set(n.id, n));

  activeFilteredNodes = [...masterNodes];
  activeFilteredEdges = [...masterEdges];

  updateStatusBadge(activeFilteredNodes.length, masterNodes.length);

  if (!graph) return;

  renderGraphData();
}

function renderGraphData() {
  if (!graph) return;

  const nodeIds = new Set(activeFilteredNodes.map(n => n.id));
  const validEdges = activeFilteredEdges
    .filter(e => {
      const src = typeof e.source === 'object' ? e.source.id : e.source;
      const tgt = typeof e.target === 'object' ? e.target.id : e.target;
      return nodeIds.has(src) && nodeIds.has(tgt);
    })
    .map(e => ({
      source: typeof e.source === 'object' ? e.source.id : e.source,
      target: typeof e.target === 'object' ? e.target.id : e.target,
      relation: e.relation
    }));

  graph.graphData({ nodes: activeFilteredNodes, links: validEdges });

  setTimeout(() => {
    graph.zoomToFit(400, 40);
  }, 100);

  updateStatusBadge(activeFilteredNodes.length, masterNodes.length);
}

function updateStatusBadge(visibleCount, totalCount) {
  const visibleEl = document.getElementById('visible-nodes-count');
  const totalEl = document.getElementById('total-nodes-count');
  if (visibleEl) visibleEl.textContent = visibleCount.toLocaleString();
  if (totalEl) totalEl.textContent = totalCount.toLocaleString();
}

export function filterGraph(type, searchQuery, rawNodes, rawEdges) {
  if (!rawNodes) return;
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
  const filteredLinks = (rawEdges || []).filter(e => {
    const src = typeof e.source === 'object' ? e.source.id : e.source;
    const tgt = typeof e.target === 'object' ? e.target.id : e.target;
    return nodeIds.has(src) && nodeIds.has(tgt);
  });

  activeFilteredNodes = [...filtered];
  activeFilteredEdges = [...filteredLinks];

  if (graph) {
    renderGraphData();
  }
}

export async function openInspector(node) {
  selectedNode = node;
  const drawer = document.getElementById('inspector-drawer');
  if (!drawer) return;

  document.getElementById('node-id').value = node.id || '';
  document.getElementById('node-label').value = node.label || '';
  document.getElementById('node-type').value = node.type || 'Concept';
  document.getElementById('node-path').value = node.path || '';
  document.getElementById('node-desc').value = node.description || 'Cargando detalles...';

  drawer.classList.remove('hidden');

  // Carga asíncrona bajo demanda de metadata detallada del nodo
  if (currentProjectId && node.id) {
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/graph/nodes/${encodeURIComponent(node.id)}`);
      if (res.ok) {
        const fullNode = await res.json();
        Object.assign(node, fullNode);

        document.getElementById('node-path').value = fullNode.path || '';
        document.getElementById('node-desc').value = fullNode.description || '';

        const metaBox = document.getElementById('node-meta-container');
        const metaGroup = document.getElementById('node-meta-group');
        if (metaBox && metaGroup) {
          const meta = fullNode.metadata || {};
          const lines = [];

          if (meta.start_line) {
            lines.push(`📍 Líneas: L${meta.start_line}${meta.end_line && meta.end_line !== meta.start_line ? ` - L${meta.end_line}` : ''}`);
          }
          if (meta.signature) {
            lines.push(`📝 Firma:\n${meta.signature}`);
          }
          if (meta.visibility) {
            lines.push(`🔒 Visibilidad: ${meta.visibility}`);
          }
          if (meta.bases && meta.bases.length) {
            lines.push(`🧬 Herencia: ${meta.bases.join(', ')}`);
          }
          if (meta.implements && meta.implements.length) {
            lines.push(`🔌 Implementa: ${meta.implements.join(', ')}`);
          }
          if (meta.columns && meta.columns.length) {
            lines.push(`📊 Columnas: ${meta.columns.join(', ')}`);
          }

          if (lines.length > 0) {
            metaBox.textContent = lines.join('\n\n');
            metaGroup.style.display = 'block';
          } else {
            metaBox.textContent = 'Sin metadata adicional.';
            metaGroup.style.display = 'block';
          }
        }
      }
    } catch (e) {
      console.warn('No se pudo cargar metadata extendida del nodo:', e);
    }
  }
}

export function closeInspector() {
  selectedNode = null;
  document.getElementById('inspector-drawer')?.classList.add('hidden');
}

