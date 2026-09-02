// Módulo Canvas / ForceGraph con Carga Bajo Demanda y Viewport Culling
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

// Almacén maestro de datos (Base de datos en memoria para el grafo activo)
let masterNodes = [];
let masterEdges = [];
let masterNodesMap = new Map();
let adjacencyMap = new Map(); // nodeId -> Set of neighbor nodeIds

// Conjunto filtrado activo
let activeFilteredNodes = [];
let activeFilteredEdges = [];

// Configuración de culling / streaming
const VIEWPORT_DELTA_RATIO = 0.35; // 35% de holgura de precarga alrededor del viewport
let cullingDebounceTimer = null;
let isInitialLayoutDone = false;

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
    .warmupTicks(120)
    .cooldownTicks(0)
    .d3AlphaDecay(0.05)
    .d3VelocityDecay(0.4)
    .minZoom(0.02)
    .maxZoom(16.0)
    .enableNodeDrag(true)
    .onNodeDrag((node, translate) => {
      node.fx = node.x;
      node.fy = node.y;
      const master = masterNodesMap.get(node.id);
      if (master) {
        master.x = node.x;
        master.y = node.y;
        master.fx = node.x;
        master.fy = node.y;
      }
    })
    .onNodeDragEnd((node, translate) => {
      node.fx = node.x;
      node.fy = node.y;
      const master = masterNodesMap.get(node.id);
      if (master) {
        master.x = node.x;
        master.y = node.y;
        master.fx = node.x;
        master.fy = node.y;
      }
      scheduleViewportCulling(50);
    })
    .enableZoomInteraction(true)
    .enablePanInteraction(true)
    .onNodeClick(node => {
      openInspector(node);
      if (onNodeSelected) onNodeSelected(node);
    })
    .onBackgroundClick(() => closeInspector())
    .onZoom(() => scheduleViewportCulling(120))
    .onZoomEnd(() => scheduleViewportCulling(0))
    .onEngineTick(() => {
      // Sincronizar coordenadas calculadas por d3 en tiempo real al mapa maestro
      const rendered = graph?.graphData()?.nodes || [];
      rendered.forEach(n => {
        if (typeof n.x === 'number' && typeof n.y === 'number') {
          const master = masterNodesMap.get(n.id);
          if (master) {
            master.x = n.x;
            master.y = n.y;
          }
        }
      });
    })
    .onEngineStop(() => {
      // Al parar la física, sincronizar coordenadas finales
      const rendered = graph?.graphData()?.nodes || [];
      rendered.forEach(n => {
        if (typeof n.x === 'number' && typeof n.y === 'number') {
          const master = masterNodesMap.get(n.id);
          if (master) {
            master.x = n.x;
            master.y = n.y;
          }
        }
      });
      isInitialLayoutDone = true;
    })
    .cooldownTicks(90);

  // Renderizado optimizado con LOD (Level of Detail)
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

    if (globalScale > 0.9 || node === selectedNode) {
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

  // Controles overlay
  document.getElementById('btn-fit')?.addEventListener('click', () => {
    // Si hay culling, cargamos momentáneamente todos para ajustar y luego re-enfocamos
    if (activeFilteredNodes.length > 0) {
      renderActiveData(activeFilteredNodes, activeFilteredEdges);
      setTimeout(() => {
        graph?.zoomToFit(400, 40);
        setTimeout(() => scheduleViewportCulling(50), 450);
      }, 50);
    }
  });

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
      graph.cooldownTicks(90);
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
        rebuildMasterIndices();
        activeFilteredNodes = activeFilteredNodes.filter(n => n.id !== deletedId);
        activeFilteredEdges = activeFilteredEdges.filter(e => e.source !== deletedId && e.target !== deletedId);
        updateVisibleNodes();
        if (onNodeDeleted) onNodeDeleted(deletedId);
      }
    } catch (e) {
      alert('Error: ' + e.message);
    }
  });

  window.addEventListener('resize', () => {
    resizeCanvas();
  });

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
      scheduleViewportCulling(100);
    }
  }
}

// Reconstruye mapas y lista de adyacencias
function rebuildMasterIndices() {
  masterNodesMap.clear();
  adjacencyMap.clear();

  masterNodes.forEach(node => {
    masterNodesMap.set(node.id, node);
    adjacencyMap.set(node.id, new Set());
  });

  // Limpiar aristas huérfanas
  masterEdges = masterEdges.filter(edge => {
    const src = typeof edge.source === 'object' ? edge.source.id : edge.source;
    const tgt = typeof edge.target === 'object' ? edge.target.id : edge.target;
    return masterNodesMap.has(src) && masterNodesMap.has(tgt);
  });

  masterEdges.forEach(edge => {
    const src = typeof edge.source === 'object' ? edge.source.id : edge.source;
    const tgt = typeof edge.target === 'object' ? edge.target.id : edge.target;
    adjacencyMap.get(src)?.add(tgt);
    adjacencyMap.get(tgt)?.add(src);
  });
}

// Carga inicial del proyecto en el almacén maestro
export function setGraphData(projectId, nodes, edges) {
  currentProjectId = projectId;
  if (!graph) return;

  masterNodes = (nodes || []).map(n => ({ ...n }));
  masterEdges = (edges || []).map(e => ({ ...e }));
  rebuildMasterIndices();

  activeFilteredNodes = [...masterNodes];
  activeFilteredEdges = [...masterEdges];
  isInitialLayoutDone = false;

  updateStatusBadge(activeFilteredNodes.length, masterNodes.length);

  // Render inicial: siempre renderizar todos los nodos activos con enlaces válidos
  const nodeIdsSet = new Set(activeFilteredNodes.map(n => n.id));
  const links = activeFilteredEdges
    .filter(e => {
      const src = typeof e.source === 'object' ? e.source.id : e.source;
      const tgt = typeof e.target === 'object' ? e.target.id : e.target;
      return nodeIdsSet.has(src) && nodeIdsSet.has(tgt);
    })
    .map(e => ({
      source: typeof e.source === 'object' ? e.source.id : e.source,
      target: typeof e.target === 'object' ? e.target.id : e.target,
      relation: e.relation
    }));

  graph.graphData({ nodes: [...activeFilteredNodes], links });

  // Sincronizar de inmediato las coordenadas calculadas por el warmup
  const initialNodes = graph.graphData().nodes || [];
  initialNodes.forEach(n => {
    const master = masterNodesMap.get(n.id);
    if (master && typeof n.x === 'number' && typeof n.y === 'number') {
      master.x = n.x;
      master.y = n.y;
    }
  });
  isInitialLayoutDone = true;

  setTimeout(() => {
    graph.zoomToFit(400, 40);
  }, 100);
}

// Programador de Culling con debounce
function scheduleViewportCulling(delayMs = 80) {
  if (cullingDebounceTimer) clearTimeout(cullingDebounceTimer);
  cullingDebounceTimer = setTimeout(() => {
    updateVisibleNodes();
  }, delayMs);
}

// Determina los nodos dentro del Viewport + Delta y sus adyacentes inmediatos
function updateVisibleNodes() {
  if (!graph || !masterNodes.length) return;

  // Si el grafo es pequeño (< 200 nodos), renderizamos todo sin culling para fluidez óptima
  if (activeFilteredNodes.length <= 200) {
    renderActiveData(activeFilteredNodes, activeFilteredEdges);
    updateStatusBadge(activeFilteredNodes.length, masterNodes.length);
    return;
  }

  // Obtener dimensiones del canvas y calcular Bounding Box en coordenadas del grafo
  const width = graph.width();
  const height = graph.height();
  const zoom = graph.zoom() || 1.0;
  const center = graph.centerAt() || { x: 0, y: 0 };

  const halfViewWidth = (width / 2) / zoom;
  const halfViewHeight = (height / 2) / zoom;

  const deltaX = halfViewWidth * VIEWPORT_DELTA_RATIO;
  const deltaY = halfViewHeight * VIEWPORT_DELTA_RATIO;

  const xMin = center.x - halfViewWidth - deltaX;
  const xMax = center.x + halfViewWidth + deltaX;
  const yMin = center.y - halfViewHeight - deltaY;
  const yMax = center.y + halfViewHeight + deltaY;

  const visibleNodeIds = new Set();

  // 1. Identificar nodos dentro de la caja [Viewport + Delta]
  activeFilteredNodes.forEach(node => {
    const master = masterNodesMap.get(node.id);
    const nx = (master && typeof master.x === 'number') ? master.x : node.x;
    const ny = (master && typeof master.y === 'number') ? master.y : node.y;

    if (typeof nx === 'number' && typeof ny === 'number') {
      if (nx >= xMin && nx <= xMax && ny >= yMin && ny <= yMax) {
        visibleNodeIds.add(node.id);
      }
    }
  });

  // Si el zoom es muy general o no se encontraron nodos en el corte, renderizar todo el conjunto activo
  if (visibleNodeIds.size === 0) {
    activeFilteredNodes.forEach(n => visibleNodeIds.add(n.id));
  }

  // 2. Streaming de Nodos Adyacentes (Vecindad 1-Hop)
  const expandedNodeIds = new Set(visibleNodeIds);
  visibleNodeIds.forEach(nodeId => {
    const neighbors = adjacencyMap.get(nodeId);
    if (neighbors) {
      neighbors.forEach(neighborId => {
        // Solo agregar si el vecino forma parte del filtro activo
        if (masterNodesMap.has(neighborId)) {
          expandedNodeIds.add(neighborId);
        }
      });
    }
  });

  // 3. Filtrar nodos y aristas a renderizar
  const nodesToRender = activeFilteredNodes.filter(n => expandedNodeIds.has(n.id));
  const activeIdsSet = new Set(nodesToRender.map(n => n.id));

  const edgesToRender = activeFilteredEdges.filter(e => {
    const src = typeof e.source === 'object' ? e.source.id : e.source;
    const tgt = typeof e.target === 'object' ? e.target.id : e.target;
    return activeIdsSet.has(src) && activeIdsSet.has(tgt);
  });

  // Actualizar dataset del canvas sin reiniciar física de posiciones fijas
  renderActiveData(nodesToRender, edgesToRender);
  updateStatusBadge(nodesToRender.length, masterNodes.length);
}

// Renderiza los datos manteniendo la identidad de objeto y coordenadas 100% estáticas (fijas)
function renderActiveData(nodes, edges) {
  if (!graph) return;

  const nodeMap = new Map();
  const preparedNodes = nodes.map(n => {
    const master = masterNodesMap.get(n.id) || n;
    // Congelar coordenadas espaciales absolutas para evitar que d3 force los empuje o reanime
    if (typeof master.x === 'number' && typeof master.y === 'number') {
      master.fx = master.x;
      master.fy = master.y;
    }
    nodeMap.set(master.id, master);
    return master;
  });

  const links = edges
    .filter(e => {
      const src = typeof e.source === 'object' ? e.source.id : e.source;
      const tgt = typeof e.target === 'object' ? e.target.id : e.target;
      return nodeMap.has(src) && nodeMap.has(tgt);
    })
    .map(e => ({
      source: typeof e.source === 'object' ? e.source.id : e.source,
      target: typeof e.target === 'object' ? e.target.id : e.target,
      relation: e.relation
    }));

  graph.graphData({ nodes: preparedNodes, links });
}

// Actualiza el contador de nodos en la vista
function updateStatusBadge(visibleCount, totalCount) {
  const visibleEl = document.getElementById('visible-nodes-count');
  const totalEl = document.getElementById('total-nodes-count');
  if (visibleEl) visibleEl.textContent = visibleCount.toLocaleString();
  if (totalEl) totalEl.textContent = totalCount.toLocaleString();
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
  const filteredLinks = rawEdges.filter(e => {
    const src = typeof e.source === 'object' ? e.source.id : e.source;
    const tgt = typeof e.target === 'object' ? e.target.id : e.target;
    return nodeIds.has(src) && nodeIds.has(tgt);
  });

  activeFilteredNodes = [...filtered];
  activeFilteredEdges = [...filteredLinks];

  updateVisibleNodes();
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

  const metaBox = document.getElementById('node-meta-container');
  const metaGroup = document.getElementById('node-meta-group');
  if (metaBox && metaGroup) {
    const meta = node.metadata || {};
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
    if (meta.docstring) {
      lines.push(`📖 Doc:\n${meta.docstring}`);
    }

    if (lines.length > 0) {
      metaBox.textContent = lines.join('\n\n');
      metaGroup.style.display = 'block';
    } else {
      metaBox.textContent = 'Sin metadata estructural capturada.';
      metaGroup.style.display = 'block';
    }
  }

  drawer.classList.remove('hidden');
}

export function closeInspector() {
  selectedNode = null;
  document.getElementById('inspector-drawer')?.classList.add('hidden');
}
