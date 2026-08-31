let cy = null;
let currentProjectId = "";
let currentGraphData = null;
let selectedNode = null;

// Initialize Cytoscape
function initCytoscape() {
  cy = cytoscape({
    container: document.getElementById('cy'),
    elements: [],
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'color': '#f0f4f8',
          'font-size': '11px',
          'text-valign': 'bottom',
          'text-margin-y': 4,
          'background-color': '#00e5ff',
          'width': 28,
          'height': 28,
          'border-width': 2,
          'border-color': '#121820'
        }
      },
      {
        selector: 'node[type = "Module"]',
        style: { 'background-color': '#3b82f6', 'shape': 'rectangle' }
      },
      {
        selector: 'node[type = "Class"]',
        style: { 'background-color': '#8b5cf6', 'shape': 'hexagon' }
      },
      {
        selector: 'node[type = "Function"]',
        style: { 'background-color': '#10b981', 'shape': 'ellipse' }
      },
      {
        selector: 'node[type = "Concept"]',
        style: { 'background-color': '#f59e0b', 'shape': 'diamond' }
      },
      {
        selector: 'node[type = "Schema"]',
        style: { 'background-color': '#ec4899', 'shape': 'round-rectangle' }
      },
      {
        selector: 'node:selected',
        style: {
          'border-color': '#fff',
          'border-width': 4,
          'shadow-blur': 12,
          'shadow-color': '#00e5ff',
          'shadow-opacity': 0.8
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': '#2a3b50',
          'target-arrow-color': '#2a3b50',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'arrow-scale': 0.8
        }
      },
      {
        selector: 'edge[relation = "calls"]',
        style: { 'line-color': '#10b981', 'target-arrow-color': '#10b981' }
      },
      {
        selector: 'edge[relation = "imports"]',
        style: { 'line-color': '#3b82f6', 'target-arrow-color': '#3b82f6' }
      },
      {
        selector: 'edge[relation = "defines"]',
        style: { 'line-color': '#8b5cf6', 'target-arrow-color': '#8b5cf6' }
      }
    ],
    layout: {
      name: 'cose',
      animate: false
    }
  });

  // Handle Node Click
  cy.on('tap', 'node', function(evt) {
    const node = evt.target;
    openInspector(node.data());
  });

  // Background Click (Close Inspector)
  cy.on('tap', function(evt) {
    if (evt.target === cy) {
      closeInspector();
    }
  });
}

// Load Projects Dropdown
async function loadProjects() {
  try {
    const res = await fetch('/api/projects');
    const projects = await res.json();
    const select = document.getElementById('project-select');
    select.innerHTML = '<option value="">Seleccionar Proyecto...</option>';

    projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.nodes_count} nodos)`;
      select.appendChild(opt);
    });

    if (projects.length > 0 && !currentProjectId) {
      select.value = projects[0].id;
      loadProjectGraph(projects[0].id);
    }
  } catch (err) {
    console.error('Error loading projects:', err);
  }
}

// Load Specific Project Graph
async function loadProjectGraph(projectId) {
  currentProjectId = projectId;
  if (!projectId) {
    cy.elements().remove();
    return;
  }

  try {
    const res = await fetch(`/api/projects/${projectId}/graph`);
    if (!res.ok) throw new Error("Could not load graph");
    currentGraphData = await res.json();

    // Render Stats
    document.getElementById('stat-nodes').textContent = currentGraphData.nodes.length;
    document.getElementById('stat-edges').textContent = currentGraphData.edges.length;

    // Format elements for Cytoscape
    const elements = [];
    currentGraphData.nodes.forEach(n => {
      elements.push({
        data: {
          id: n.id,
          label: n.label,
          type: n.type,
          path: n.path,
          description: n.description,
          community: n.community
        }
      });
    });

    currentGraphData.edges.forEach((e, i) => {
      elements.push({
        data: {
          id: `edge-${i}`,
          source: e.source,
          target: e.target,
          relation: e.relation
        }
      });
    });

    cy.elements().remove();
    cy.add(elements);
    cy.layout({ name: 'cose', padding: 50, animate: false }).run();

    // Load Markdown Report
    loadProjectReport(projectId);

  } catch (err) {
    console.error("Error loading project graph:", err);
  }
}

// Load Markdown Report
async function loadProjectReport(projectId) {
  try {
    const res = await fetch(`/api/projects/${projectId}/graph/report`);
    const data = await res.json();
    const container = document.getElementById('report-container');
    if (window.marked) {
      container.innerHTML = marked.parse(data.report);
    } else {
      container.innerText = data.report;
    }
  } catch (err) {
    console.error("Error loading report:", err);
  }
}

// Open Inspector Drawer
function openInspector(data) {
  selectedNode = data;
  document.getElementById('node-id').value = data.id || '';
  document.getElementById('node-label').value = data.label || '';
  document.getElementById('node-type').value = data.type || 'Concept';
  document.getElementById('node-path').value = data.path || '';
  document.getElementById('node-desc').value = data.description || '';
  document.getElementById('inspector').classList.remove('hidden');
}

function closeInspector() {
  selectedNode = null;
  document.getElementById('inspector').classList.add('hidden');
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
  initCytoscape();
  loadProjects();

  // Project Switch
  document.getElementById('project-select').addEventListener('change', (e) => {
    loadProjectGraph(e.target.value);
  });

  // Tab Switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).style.display = 'block';
    });
  });

  // Filter Node Types
  document.getElementById('filter-node-type').addEventListener('change', (e) => {
    const val = e.target.value;
    if (val === 'ALL') {
      cy.nodes().show();
    } else {
      cy.nodes().hide();
      cy.nodes(`[type = "${val}"]`).show();
    }
  });

  // Canvas Actions
  document.getElementById('btn-fit').addEventListener('click', () => cy.fit());
  document.getElementById('btn-layout-cose').addEventListener('click', () => cy.layout({ name: 'cose', animate: true }).run());
  document.getElementById('btn-close-inspector').addEventListener('click', closeInspector);

  // Save Node Edits
  document.getElementById('btn-save-node').addEventListener('click', async () => {
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
        const cyNode = cy.getElementById(selectedNode.id);
        cyNode.data(updateData);
        alert('Nodo actualizado correctamente.');
      }
    } catch (err) {
      alert('Error guardando nodo: ' + err.message);
    }
  });

  // Delete Node
  document.getElementById('btn-delete-node').addEventListener('click', async () => {
    if (!selectedNode || !currentProjectId) return;
    if (!confirm(`¿Eliminar nodo ${selectedNode.id}?`)) return;

    try {
      const res = await fetch(`/api/projects/${currentProjectId}/graph/nodes/${encodeURIComponent(selectedNode.id)}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        cy.remove(cy.getElementById(selectedNode.id));
        closeInspector();
      }
    } catch (err) {
      alert('Error eliminando nodo: ' + err.message);
    }
  });

  // Modal: New Project
  const modalProj = document.getElementById('modal-project');
  document.getElementById('btn-new-project').addEventListener('click', () => modalProj.classList.remove('hidden'));
  document.getElementById('btn-cancel-proj').addEventListener('click', () => modalProj.classList.add('hidden'));
  document.getElementById('btn-confirm-proj').addEventListener('click', async () => {
    const id = document.getElementById('new-proj-id').value.trim();
    const name = document.getElementById('new-proj-name').value.trim();
    if (!id) return alert('Ingresa un ID');

    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: id, name: name || id })
      });
      if (res.ok) {
        modalProj.classList.add('hidden');
        await loadProjects();
        document.getElementById('project-select').value = id;
        loadProjectGraph(id);
      }
    } catch (err) {
      alert('Error creando proyecto: ' + err.message);
    }
  });

  // Modal: Ingest Directory
  const modalIngest = document.getElementById('modal-ingest');
  document.getElementById('btn-ingest-dir').addEventListener('click', () => {
    if (!currentProjectId) return alert('Selecciona o crea un proyecto primero');
    document.getElementById('ingest-proj-id').value = currentProjectId;
    modalIngest.classList.remove('hidden');
  });
  document.getElementById('btn-cancel-ingest').addEventListener('click', () => modalIngest.classList.add('hidden'));
  document.getElementById('btn-confirm-ingest').addEventListener('click', async () => {
    const path = document.getElementById('ingest-dir-path').value.trim();
    if (!path) return alert('Ingresa una ruta de directorio');

    const btn = document.getElementById('btn-confirm-ingest');
    btn.textContent = 'Escaneando...';
    btn.disabled = true;

    try {
      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: currentProjectId,
          source_directory: path
        })
      });
      const data = await res.json();
      if (res.ok) {
        modalIngest.classList.add('hidden');
        alert(`Indexación exitosa: ${data.nodes_count} nodos y ${data.edges_count} conexiones encontradas.`);
        await loadProjects();
        loadProjectGraph(currentProjectId);
      } else {
        alert('Error: ' + data.detail);
      }
    } catch (err) {
      alert('Error indexando directorio: ' + err.message);
    } finally {
      btn.textContent = 'Iniciar Escaneo';
      btn.disabled = false;
    }
  });
});
