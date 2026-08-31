// Módulo de Resumen / Métricas
export function renderSummary(graphData, onFilterChange) {
  if (!graphData) return;

  document.getElementById('summary-stat-nodes').textContent = graphData.nodes?.length || 0;
  document.getElementById('summary-stat-edges').textContent = graphData.edges?.length || 0;
  
  const totalFiles = graphData.metadata?.total_files || 0;
  document.getElementById('summary-stat-files').textContent = totalFiles;

  const fileTypes = graphData.metadata?.file_types || {};
  const breakdownContainer = document.getElementById('summary-breakdown-list');
  if (breakdownContainer) {
    let html = '';
    const keys = Object.keys(fileTypes);
    if (keys.length > 0) {
      keys.forEach(k => {
        html += `
          <div class="breakdown-item">
            <span class="breakdown-ext">${k}</span>
            <span class="breakdown-count">${fileTypes[k]} archivos</span>
          </div>
        `;
      });
    } else {
      html = '<em style="color:var(--text-muted); font-size:12px;">Sin desglose de tipos.</em>';
    }
    breakdownContainer.innerHTML = html;
  }

  // Event Listeners de Filtros
  const selectFilter = document.getElementById('summary-filter-type');
  const searchInput = document.getElementById('summary-search-nodes');

  const trigger = () => {
    if (onFilterChange) {
      onFilterChange(selectFilter?.value || 'ALL', searchInput?.value || '');
    }
  };

  selectFilter?.addEventListener('change', trigger);
  searchInput?.addEventListener('input', trigger);
}
