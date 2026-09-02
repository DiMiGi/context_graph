// Orquestador Principal de la Aplicación Web con Enrutamiento SPA y Carga Diferida
import { initCanvas, isCanvasInitialized, pauseCanvas, resumeCanvas, setGraphData, filterGraph, resizeCanvas } from '/views/canvas/canvas.js?t=1788380000';
import { renderSummary } from '/views/summary/summary.js';
import { loadReport } from '/views/report/report.js';
import { renderUnregistered } from '/views/unregistered/unregistered.js';
import { enqueueReindexTask, startTasksPolling, fetchTasks } from '/views/tasks/tasks.js';

// Mapeo bidireccional entre Vistas DOM y Rutas URL
const VIEW_ROUTES = {
  'view-canvas': 'graphs',
  'view-summary': 'summary',
  'view-report': 'report',
  'view-unregistered': 'unregistered',
  'view-tasks': 'tasks'
};

const ROUTE_TO_VIEW = {
  'graphs': 'view-canvas',
  'graph': 'view-canvas',
  'summary': 'view-summary',
  'report': 'view-report',
  'unregistered': 'view-unregistered',
  'tasks': 'view-tasks'
};

let currentViewId = 'view-canvas';
let currentProjectId = "";
let rawGraphData = null;
let projectsList = [];

// 1. Analizar Ruta Actual desde window.location.pathname
function parseUrlRoute() {
  const path = window.location.pathname.replace(/^\/+|\/+$/g, '');
  if (!path) {
    return { viewId: 'view-canvas', projectId: null };
  }
  const parts = path.split('/');
  const route = parts[0]?.toLowerCase();
  const projParam = parts.slice(1).join('/');

  const viewId = ROUTE_TO_VIEW[route] || 'view-canvas';
  return { viewId, projectId: projParam ? decodeURIComponent(projParam) : null };
}

// 2. Resolver project_id por coincidencia exacta, nombre o sufijo
function resolveProjectId(param) {
  if (!param || !projectsList.length) return null;
  const clean = param.toLowerCase().trim();
  
  // Coincidencia exacta por ID
  let match = projectsList.find(p => (p.id || '').toLowerCase() === clean);
  if (match) return match.id;

  // Coincidencia exacta por nombre
  match = projectsList.find(p => (p.name || '').toLowerCase() === clean);
  if (match) return match.id;

  // Coincidencia por sufijo (ej: "discord_api" -> "space_engineers_discord_api")
  match = projectsList.find(p => (p.id || '').toLowerCase().endsWith(clean));
  if (match) return match.id;

  // Coincidencia por contención
  match = projectsList.find(p => (p.id || '').toLowerCase().includes(clean));
  if (match) return match.id;

  return null;
}

// 3. Actualizar la barra de direcciones del navegador
function updateBrowserUrl(replace = false) {
  const routeSegment = VIEW_ROUTES[currentViewId] || 'graphs';
  const newPath = currentProjectId ? `/${routeSegment}/${encodeURIComponent(currentProjectId)}` : `/${routeSegment}`;
  
  if (window.location.pathname !== newPath) {
    if (replace) {
      history.replaceState({ viewId: currentViewId, projectId: currentProjectId }, '', newPath);
    } else {
      history.pushState({ viewId: currentViewId, projectId: currentProjectId }, '', newPath);
    }
  }
}

// 4. Cambiar entre Vistas Modulares (Lazy Canvas)
export function switchView(viewId, updateUrl = true) {
  currentViewId = viewId;

  // Actualizar botones de navegación
  document.querySelectorAll('.nav-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.view === viewId);
  });

  // Mostrar contenedor correspondiente
  document.querySelectorAll('.view-module').forEach(v => {
    if (v.id === viewId) {
      v.classList.remove('hidden');
      v.classList.add('active');
    } else {
      v.classList.add('hidden');
      v.classList.remove('active');
    }
  });

  // Inicialización o reanudación diferida del Canvas
  if (viewId === 'view-canvas') {
    if (!isCanvasInitialized()) {
      initCanvas('graph-canvas-element', null, (deletedId) => {
        loadProjectData(currentProjectId);
      });
    } else {
      resumeCanvas();
    }
    setTimeout(() => resizeCanvas(), 50);
  } else {
    // Si no estamos en la vista de grafo, pausamos la física para ahorrar CPU/GPU
    pauseCanvas();
    if (viewId === 'view-tasks') {
      fetchTasks();
    } else if (viewId === 'view-report' && currentProjectId) {
      loadReport(currentProjectId);
    }
  }

  if (updateUrl) {
    updateBrowserUrl(false);
  }
}

// 5. Cargar Datos del Proyecto Activo
async function loadProjectData(projectId) {
  currentProjectId = projectId;
  const select = document.getElementById('project-select');
  if (select && select.value !== projectId) {
    select.value = projectId;
  }
  updateBrowserUrl(true);

  if (!projectId) return;

  try {
    const res = await fetch(`/api/projects/${projectId}/graph/geometry`);
    if (!res.ok) {
      // Fallback a endpoint de grafo completo
      const fallbackRes = await fetch(`/api/projects/${projectId}/graph`);
      if (!fallbackRes.ok) {
        rawGraphData = { nodes: [], edges: [], metadata: {} };
        setGraphData(projectId, [], []);
        renderSummary(rawGraphData);
        renderUnregistered({});
        return;
      }
      rawGraphData = await fallbackRes.json();
    } else {
      rawGraphData = await res.json();
    }

    // Actualizar datos del grafo en memoria
    setGraphData(projectId, rawGraphData.nodes || [], rawGraphData.edges || []);

    // Si el usuario ya está viendo el canvas, inicializarlo si aún no lo estaba
    if (currentViewId === 'view-canvas' && !isCanvasInitialized()) {
      initCanvas('graph-canvas-element', null, (deletedId) => {
        loadProjectData(currentProjectId);
      });
    }

    // Actualizar Módulos secundarios
    renderSummary(rawGraphData, (type, q) => {
      filterGraph(type, q, rawGraphData.nodes, rawGraphData.edges);
      if (currentViewId !== 'view-canvas') {
        switchView('view-canvas');
      }
    });
    renderUnregistered(rawGraphData.metadata?.unregistered_files);
    loadReport(projectId);

  } catch (err) {
    console.error("Error al cargar datos del proyecto:", err);
  }
}

// 6. Cargar Lista de Proyectos y Resolver Ruta Inicial
async function loadProjects(preferredProjectId = null) {
  try {
    const res = await fetch('/api/projects');
    projectsList = await res.json();
    const select = document.getElementById('project-select');
    select.innerHTML = '<option value="">Seleccionar Proyecto...</option>';

    projectsList.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      const countLabel = p.nodes_count > 0 ? `(${p.nodes_count} nodos)` : `(Sin indexar)`;
      opt.textContent = `${p.name} ${countLabel}`;
      select.appendChild(opt);
    });

    // Resolver qué proyecto seleccionar
    let targetProj = resolveProjectId(preferredProjectId) 
      || currentProjectId 
      || (projectsList.length > 0 ? projectsList[0].id : "");

    if (targetProj) {
      select.value = targetProj;
      await loadProjectData(targetProj);
    }
  } catch (err) {
    console.error('Error cargando proyectos:', err);
  }
}

// 7. Inicialización Principal
document.addEventListener('DOMContentLoaded', async () => {
  // 1. Obtener vista y proyecto desde la URL
  const initialRoute = parseUrlRoute();

  // 2. Cambiar a la vista solicitada (si no es canvas, el canvas NO se inicializa)
  switchView(initialRoute.viewId, false);

  // 3. Cargar proyectos y datos del proyecto indicado en la URL
  await loadProjects(initialRoute.projectId);

  // 4. Polling de tareas asíncronas
  startTasksPolling((completedProjectId) => {
    loadProjects(currentProjectId);
    if (completedProjectId === currentProjectId) {
      loadProjectData(currentProjectId);
    }
  });

  // 5. Navegación por pestañas
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => switchView(tab.dataset.view, true));
  });

  // 6. Cambio de proyecto en el desplegable
  document.getElementById('project-select')?.addEventListener('change', (e) => {
    loadProjectData(e.target.value);
  });

  // 7. Soporte para botones Atrás/Adelante del navegador (Popstate)
  window.addEventListener('popstate', () => {
    const route = parseUrlRoute();
    const matchedProj = resolveProjectId(route.projectId);
    switchView(route.viewId, false);
    if (matchedProj && matchedProj !== currentProjectId) {
      loadProjectData(matchedProj);
    }
  });

  // 8. Botones de acciones asíncronas
  document.getElementById('btn-reindex-inc')?.addEventListener('click', async () => {
    if (!currentProjectId) return alert('Selecciona un proyecto');
    const res = await enqueueReindexTask(currentProjectId, 'incremental');
    alert(res.message || 'Tarea encolada');
    switchView('view-tasks');
  });

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

  document.getElementById('btn-rebuild-full')?.addEventListener('click', async () => {
    if (!currentProjectId) return alert('Selecciona un proyecto');
    if (confirm('⚠️ ¿Estás seguro de reconstruir el grafo?\nLa tarea se ejecutará en segundo plano.')) {
      const res = await enqueueReindexTask(currentProjectId, 'rebuild');
      alert(res.message || 'Tarea encolada');
      switchView('view-tasks');
    }
  });

  document.getElementById('btn-refresh-tasks')?.addEventListener('click', () => fetchTasks());
  document.getElementById('btn-refresh-report')?.addEventListener('click', () => loadReport(currentProjectId));
});
