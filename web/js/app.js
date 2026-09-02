// Orquestador Principal de la Aplicación Web Modular
import { initCanvas, setGraphData, filterGraph, resizeCanvas } from '/views/canvas/canvas.js';
import { renderSummary } from '/views/summary/summary.js';
import { loadReport } from '/views/report/report.js';
import { renderUnregistered } from '/views/unregistered/unregistered.js';
import { enqueueReindexTask, startTasksPolling, fetchTasks } from '/views/tasks/tasks.js';

let currentProjectId = "";
let rawGraphData = null;

// 1. Cargar Lista de Proyectos
async function loadProjects(targetProjectId = null) {
  try {
    const res = await fetch('/api/projects');
    const projects = await res.json();
    const select = document.getElementById('project-select');
    select.innerHTML = '<option value="">Seleccionar Proyecto...</option>';

    projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      const countLabel = p.nodes_count > 0 ? `(${p.nodes_count} nodos)` : `(Sin indexar)`;
      opt.textContent = `${p.name} ${countLabel}`;
      select.appendChild(opt);
    });

    const activeToSelect = targetProjectId || currentProjectId || (projects.length > 0 ? projects[0].id : "");
    if (activeToSelect) {
      select.value = activeToSelect;
      if (!currentProjectId || targetProjectId) {
        loadProjectData(activeToSelect);
      }
    }
  } catch (err) {
    console.error('Error cargando proyectos:', err);
  }
}

// 3. Cargar Datos del Proyecto Activo
async function loadProjectData(projectId) {
  currentProjectId = projectId;
  if (!projectId) return;

  try {
    const res = await fetch(`/api/projects/${projectId}/graph`);
    if (!res.ok) {
      rawGraphData = { nodes: [], edges: [], metadata: {} };
      setGraphData(projectId, [], []);
      renderSummary(rawGraphData);
      renderUnregistered({});
      return;
    }

    rawGraphData = await res.json();

    // Actualizar Módulos
    setGraphData(projectId, rawGraphData.nodes || [], rawGraphData.edges || []);
    renderSummary(rawGraphData, (type, q) => {
      filterGraph(type, q, rawGraphData.nodes, rawGraphData.edges);
    });
    renderUnregistered(rawGraphData.metadata?.unregistered_files);
    loadReport(projectId);

  } catch (err) {
    console.error("Error al cargar datos del proyecto:", err);
  }
}

// 4. Cambiar entre Vistas de la Barra Superior
function switchView(viewId) {
  document.querySelectorAll('.nav-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.view === viewId);
  });

  document.querySelectorAll('.view-module').forEach(v => {
    if (v.id === viewId) {
      v.classList.remove('hidden');
      v.classList.add('active');
    } else {
      v.classList.add('hidden');
      v.classList.remove('active');
    }
  });

  if (viewId === 'view-canvas') {
    setTimeout(() => resizeCanvas(), 50);
  } else if (viewId === 'view-tasks') {
    fetchTasks();
  }
}

// 5. Inicialización Principal
document.addEventListener('DOMContentLoaded', async () => {
  // 1. Inicializar Canvas ForceGraph en su contenedor montado
  initCanvas('graph-canvas-element', null, (deletedId) => {
    loadProjectData(currentProjectId);
  });

  // 2. Cargar Proyectos y Datos del grafo inicial
  await loadProjects();
  startTasksPolling((completedProjectId) => {
    loadProjects();
    if (completedProjectId === currentProjectId) {
      loadProjectData(currentProjectId);
    }
  });

  // 3. Navegación Pestañas Superiores
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => switchView(tab.dataset.view));
  });

  // Selector de Proyecto
  document.getElementById('project-select')?.addEventListener('change', (e) => {
    loadProjectData(e.target.value);
  });

  // Botón: Indexar Nuevos (Asíncrono vía Tasks)
  document.getElementById('btn-reindex-inc')?.addEventListener('click', async () => {
    if (!currentProjectId) return alert('Selecciona un proyecto');
    const res = await enqueueReindexTask(currentProjectId, 'incremental');
    alert(res.message || 'Tarea encolada');
    switchView('view-tasks');
  });

  // Botón: Reindexar Rutas Específicas
  document.getElementById('btn-reindex-partial')?.addEventListener('click', async () => {
    if (!currentProjectId) return alert('Selecciona un proyecto');
    const input = prompt('Rutas a reindexar (ej: apps/backend/app/Models, routes/api.php):');
    if (!input) return;
    const paths = input.split(',').map(p => p.trim()).filter(p => p);
    if (paths.length > 0) {
      const res = await enqueueReindexTask(currentProjectId, 'partial', paths);
      alert(res.message || 'Tarea encolada');
      switchView('view-tasks');
    }
  });

  // Botón: Reconstruir Todo (Purga y escaneo asíncrono)
  document.getElementById('btn-rebuild-full')?.addEventListener('click', async () => {
    if (!currentProjectId) return alert('Selecciona un proyecto');
    if (confirm('⚠️ ¿Estás seguro de reconstruir el grafo?\nLa tarea se ejecutará en segundo plano.')) {
      const res = await enqueueReindexTask(currentProjectId, 'rebuild');
      alert(res.message || 'Tarea encolada');
      switchView('view-tasks');
    }
  });

  // Botón recargar tareas
  document.getElementById('btn-refresh-tasks')?.addEventListener('click', () => fetchTasks());
  document.getElementById('btn-refresh-report')?.addEventListener('click', () => loadReport(currentProjectId));
});
