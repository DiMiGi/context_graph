// Módulo de Archivos No Registrados
export function renderUnregistered(unregisteredMap) {
  const container = document.getElementById('unregistered-table-wrapper');
  if (!container) return;

  const unreg = unregisteredMap || {};
  const keys = Object.keys(unreg);

  if (keys.length > 0) {
    let html = '<table style="width:100%; font-size:13px; border-collapse:collapse;">';
    html += '<thead><tr style="border-bottom:1px solid var(--border-color); text-align:left;"><th style="padding:10px;">Extensión</th><th style="padding:10px;">Cantidad de Archivos</th></tr></thead><tbody>';
    keys.forEach(k => {
      html += `<tr><td style="padding:10px; font-family:var(--font-mono); color:var(--accent-warning);">${k}</td><td style="padding:10px;">${unreg[k]}</td></tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
  } else {
    container.innerHTML = '<em style="color:var(--text-muted); font-size:13px;">Todos los archivos del repositorio están categorizados con analizador semántico.</em>';
  }
}
