// Módulo de Tareas Asíncronas
let pollingInterval = null;
const knownTaskStatuses = new Map();

export async function fetchTasks(onTaskCompleted) {
  const container = document.getElementById('tasks-list-card');
  const badge = document.getElementById('task-badge');
  if (!container) return;

  try {
    const res = await fetch('/api/tasks');
    const tasks = await res.json();

    const activeCount = tasks.filter(t => t.status === 'running' || t.status === 'queued').length;
    if (badge) {
      badge.textContent = activeCount;
      badge.classList.toggle('hidden', activeCount === 0);
    }

    if (tasks.length === 0) {
      container.innerHTML = '<em style="color:var(--text-muted); font-size:13px;">No hay tareas registradas en esta sesión.</em>';
      return;
    }

    let html = '<table style="width:100%; font-size:13px; border-collapse:collapse;">';
    html += '<thead><tr style="border-bottom:1px solid var(--border-color); text-align:left;">';
    html += '<th style="padding:10px;">ID Tarea</th>';
    html += '<th style="padding:10px;">Proyecto</th>';
    html += '<th style="padding:10px;">Rama</th>';
    html += '<th style="padding:10px;">Modo</th>';
    html += '<th style="padding:10px;">Estado</th>';
    html += '<th style="padding:10px;">Resultado</th>';
    html += '</tr></thead><tbody>';

    tasks.forEach(t => {
      const pillClass = `task-status-pill ${t.status}`;
      let resultText = '-';
      if (t.status === 'completed' && t.result) {
        resultText = `✅ ${t.result.nodes_count} nodos, ${t.result.edges_count} edges (${t.result.new_files_parsed} nuevos)`;
      } else if (t.status === 'failed') {
        resultText = `❌ ${t.error || 'Error'}`;
      } else if (t.status === 'running') {
        resultText = `⏳ Procesando en segundo plano...`;
      }

      const branchLabel = t.branch || t.result?.branch || 'main';

      html += `
        <tr style="border-bottom:1px solid var(--bg-panel);">
          <td style="padding:10px; font-family:var(--font-mono); color:var(--text-muted);">${t.id.slice(0, 8)}...</td>
          <td style="padding:10px; font-weight:600;">${t.project_id}</td>
          <td style="padding:10px; font-family:var(--font-mono); color:var(--accent-primary);">🌿 ${branchLabel}</td>
          <td style="padding:10px; font-family:var(--font-mono);">${t.mode}</td>
          <td style="padding:10px;"><span class="${pillClass}">${t.status}</span></td>
          <td style="padding:10px; color:var(--text-muted);">${resultText}</td>
        </tr>
      `;
    });

    // Detectar tareas recién completadas para auto-recargar vistas
    tasks.forEach(t => {
      const prevStatus = knownTaskStatuses.get(t.id);
      if (prevStatus && prevStatus !== 'completed' && t.status === 'completed') {
        if (onTaskCompleted) onTaskCompleted(t.project_id, t);
      }
      knownTaskStatuses.set(t.id, t.status);
    });

    html += '</tbody></table>';
    container.innerHTML = html;

  } catch (err) {
    container.innerHTML = `<p style="color:var(--accent-danger);">Error consultando tareas: ${err.message}</p>`;
  }
}

export function startTasksPolling(onTaskCompleted) {
  if (pollingInterval) clearInterval(pollingInterval);
  fetchTasks(onTaskCompleted);
  pollingInterval = setInterval(() => fetchTasks(onTaskCompleted), 2000);
}

export function stopTasksPolling() {
  if (pollingInterval) clearInterval(pollingInterval);
}

export async function enqueueReindexTask(projectId, mode, targetPaths = null, branch = null) {
  const res = await fetch(`/api/tasks/projects/${projectId}/reindex`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-By': 'web_ui'
    },
    body: JSON.stringify({ mode, target_paths: targetPaths, branch })
  });
  return await res.json();
}
