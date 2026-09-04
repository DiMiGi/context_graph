// Orquestador Principal de la Aplicación Web con Enrutamiento SPA, Multi-Rama y Carga Diferida
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
let currentBranch = "";
let rawGraphData = null;
let projectsList = [];

// 1. Analizar Ruta Actual desde window.location.pathname
function parseUrlRoute() {
  const path = window.location.pathname.replace(/^\/+|\/+$/g, '');
  if (!path) {
    return { viewId: 'view-canvas', projectId: null, branch: null };
  }
  const parts = path.split('/');
  const route = parts[0]?.toLowerCase();
  const projParam = parts[1] ? decodeURIComponent(parts[1]) : null;
  const branchParam = parts[2] ? decodeURIComponent(parts[2]) : null;

  const viewId = ROUTE_TO_VIEW[route] || 'view-canvas';
  return { viewId, projectId: projParam, branch: branchParam };
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

  // Coincidencia por sufijo
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
  let newPath = `/${routeSegment}`;
  if (currentProjectId) {
    newPath += `/${encodeURIComponent(currentProjectId)}`;
    if (currentBranch) {
      newPath += `/${encodeURIComponent(currentBranch)}`;
    }
  }
  
  if (window.location.pathname !== newPath) {
    if (replace) {
      history.replaceState({ viewId: currentViewId, projectId: currentProjectId, branch: currentBranch }, '', newPath);
    } else {
      history.pushState({ viewId: currentViewId, projectId: currentProjectId, branch: currentBranch }, '', newPath);
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
        loadProjectData(currentProjectId, currentBranch);
      });
    } else {
      resumeCanvas();
    }
    setTimeout(() => resizeCanvas(), 50);
  } else {
    pauseCanvas();
    if (viewId === 'view-tasks') {
      fetchTasks();
    } else if (viewId === 'view-report' && currentProjectId) {
      loadReport(currentProjectId, currentBranch);
    }
  }

  if (updateUrl) {
    updateBrowserUrl(false);
  }
}

// 5. Cargar Ramas Disponibles para el Proyecto
async function loadBranchesForProject(projectId, preferredBranch = null) {
  const branchSelect = document.getElementById('branch-select');
  if (!branchSelect || !projectId) return "main";

  try {
    const res = await fetch(`/api/projects/${projectId}/branches`);
    if (!res.ok) throw new Error('Error al consultar ramas');
    const data = await res.json();
    
    branchSelect.innerHTML = '';
    const activeBranch = data.active_branch || "main";
    const branches = data.branches || [];

    // Si no hay ramas indexadas aún, agregar al menos la rama activa de git
    if (branches.length === 0) {
      const opt = document.createElement('option');
      opt.value = activeBranch;
      opt.textContent = `${activeBranch} (activa)`;
      branchSelect.appendChild(opt);
      currentBranch = activeBranch;
      return currentBranch;
    }

    branches.forEach(b => {
      const opt = document.createElement('option');
      opt.value = b.branch;
      const isActive = b.is_active || b.branch === activeBranch;
      const shortHash = b.short_hash ? ` [${b.short_hash}]` : '';
      let statusLabel = '';
      if (isActive && b.is_indexed) {
        statusLabel = ` 🟢 (activa - ${b.nodes_count} nodos)`;
      } else if (isActive && !b.is_indexed) {
        statusLabel = ` 🟢 (activa - sin indexar)`;
      } else if (b.is_indexed) {
        statusLabel = ` 🌿 (${b.nodes_count} nodos)`;
      } else {
        statusLabel = ` ⚪ (sin indexar)`;
      }
      opt.textContent = `${b.branch}${shortHash}${statusLabel}`;
      branchSelect.appendChild(opt);
    });

    // Determinar rama seleccionada
    let targetBranch = preferredBranch;
    if (!targetBranch || !branches.some(b => b.branch === targetBranch)) {
      targetBranch = activeBranch || (branches[0]?.branch) || "main";
    }

    branchSelect.value = targetBranch;
    currentBranch = targetBranch;
    return currentBranch;

  } catch (err) {
    console.error("Error cargando ramas:", err);
    currentBranch = preferredBranch || "main";
    return currentBranch;
  }
}

// 6. Cargar Datos del Proyecto Activo y Rama
async function loadProjectData(projectId, branch = null) {
  currentProjectId = projectId;
  const projectSelect = document.getElementById('project-select');
  if (projectSelect && projectSelect.value !== projectId) {
    projectSelect.value = projectId;
  }

  if (!projectId) return;

  // Si no se pasó rama explícita o necesitamos refrescar el selector de ramas
  if (!branch) {
    branch = await loadBranchesForProject(projectId, currentBranch);
  }
  currentBranch = branch;

  const branchSelect = document.getElementById('branch-select');
  if (branchSelect && branchSelect.value !== currentBranch) {
    branchSelect.value = currentBranch;
  }

  updateBrowserUrl(true);

  try {
    const branchParam = currentBranch ? `?branch=${encodeURIComponent(currentBranch)}` : '';
    const res = await fetch(`/api/projects/${projectId}/graph/geometry${branchParam}`);
    if (!res.ok) {
      // Fallback a endpoint de grafo completo
      const fallbackRes = await fetch(`/api/projects/${projectId}/graph${branchParam}`);
      if (!fallbackRes.ok) {
        rawGraphData = { nodes: [], edges: [], metadata: { branch: currentBranch } };
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
        loadProjectData(currentProjectId, currentBranch);
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
    loadReport(projectId, currentBranch);

  } catch (err) {
    console.error("Error al cargar datos del proyecto:", err);
  }
}

// 7. Cargar Lista de Proyectos y Resolver Ruta Inicial
async function loadProjects(preferredProjectId = null, preferredBranch = null) {
  try {
    const res = await fetch('/api/projects');
    projectsList = await res.json();
    const select = document.getElementById('project-select');
    select.innerHTML = '<option value="">Seleccionar Proyecto...</option>';

    projectsList.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      const countLabel = p.nodes_count > 0 ? `(${p.nodes_count} nodos)` : `(Sin indexar)`;
      const branchBadge = p.git_branch ? `[🌿 ${p.git_branch}]` : '';
      opt.textContent = `${p.name} ${branchBadge} ${countLabel}`;
      select.appendChild(opt);
    });

    // Resolver qué proyecto seleccionar
    let targetProj = resolveProjectId(preferredProjectId) 
      || currentProjectId 
      || (projectsList.length > 0 ? projectsList[0].id : "");

    if (targetProj) {
      select.value = targetProj;
      await loadBranchesForProject(targetProj, preferredBranch);
      await loadProjectData(targetProj, currentBranch);
    }
  } catch (err) {
    console.error('Error cargando proyectos:', err);
  }
}

// 8. Inicialización Principal
document.addEventListener('DOMContentLoaded', async () => {
  // 1. Obtener vista, proyecto y rama desde la URL
  const initialRoute = parseUrlRoute();

  // 2. Cambiar a la vista solicitada
  switchView(initialRoute.viewId, false);

  // 3. Cargar proyectos y datos del proyecto/rama indicado en la URL
  await loadProjects(initialRoute.projectId, initialRoute.branch);

  // 4. Polling de tareas asíncronas
  startTasksPolling((completedProjectId, completedTask) => {
    loadProjects(currentProjectId, currentBranch);
    if (completedProjectId === currentProjectId) {
      loadProjectData(currentProjectId, currentBranch);
    }
  });

  // 5. Navegación por pestañas
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => switchView(tab.dataset.view, true));
  });

  // 6. Cambio de proyecto en el desplegable
  document.getElementById('project-select')?.addEventListener('change', async (e) => {
    const newProj = e.target.value;
    if (newProj) {
      await loadBranchesForProject(newProj);
      await loadProjectData(newProj, currentBranch);
    }
  });

  // 7. Cambio de rama en el desplegable
  document.getElementById('branch-select')?.addEventListener('change', (e) => {
    currentBranch = e.target.value;
    loadProjectData(currentProjectId, currentBranch);
  });

  // 8. Soporte para botones Atrás/Adelante del navegador (Popstate)
  window.addEventListener('popstate', () => {
    const route = parseUrlRoute();
    const matchedProj = resolveProjectId(route.projectId);
    switchView(route.viewId, false);
    if (matchedProj && (matchedProj !== currentProjectId || route.branch !== currentBranch)) {
      loadProjectData(matchedProj, route.branch);
    }
  });

  // 9. Botones de acciones asíncronas
  document.getElementById('btn-reindex-inc')?.addEventListener('click', async () => {
    if (!currentProjectId) return alert('Selecciona un proyecto');
    const res = await enqueueReindexTask(currentProjectId, 'incremental', null, currentBranch);
    alert(res.message || 'Tarea encolada');
    switchView('view-tasks');
  });

  document.getElementById('btn-reindex-partial')?.addEventListener('click', async () => {
    if (!currentProjectId) return alert('Selecciona un proyecto');
    const input = prompt('Rutas a reindexar (ej: apps/backend/app/Models, routes/api.php):');
    if (!input) return;
    const paths = input.split(',').map(p => p.trim()).filter(p => p);
    if (paths.length > 0) {
      const res = await enqueueReindexTask(currentProjectId, 'partial', paths, currentBranch);
      alert(res.message || 'Tarea encolada');
      switchView('view-tasks');
    }
  });

  document.getElementById('btn-rebuild-full')?.addEventListener('click', async () => {
    if (!currentProjectId) return alert('Selecciona un proyecto');
    if (confirm(`⚠️ ¿Estás seguro de reconstruir el grafo para la rama '${currentBranch || 'activa'}'?\nLa tarea se ejecutará en segundo plano.`)) {
      const res = await enqueueReindexTask(currentProjectId, 'rebuild', null, currentBranch);
      alert(res.message || 'Tarea encolada');
      switchView('view-tasks');
    }
  });

  document.getElementById('btn-refresh-tasks')?.addEventListener('click', () => fetchTasks());
  document.getElementById('btn-refresh-report')?.addEventListener('click', () => loadReport(currentProjectId, currentBranch));
});
