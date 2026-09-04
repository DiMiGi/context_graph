// Módulo de Reporte Markdown
export async function loadReport(projectId, branch = null) {
  const container = document.getElementById('report-content-body');
  if (!container || !projectId) return;

  try {
    container.innerHTML = '<p style="color:var(--text-muted);">Cargando reporte arquitectónico...</p>';
    const branchParam = branch ? `?branch=${encodeURIComponent(branch)}` : '';
    const res = await fetch(`/api/projects/${projectId}/graph/report${branchParam}`);
    const data = await res.json();
    if (window.marked && data.report) {
      container.innerHTML = marked.parse(data.report);
    } else {
      container.innerHTML = `<pre style="white-space:pre-wrap; padding:16px;">${data.report || 'Sin contenido de reporte.'}</pre>`;
    }
  } catch (err) {
    container.innerHTML = `<p style="color:var(--accent-danger);">Error al cargar reporte: ${err.message}</p>`;
  }
}
