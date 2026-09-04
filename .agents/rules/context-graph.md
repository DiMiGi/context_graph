---
trigger: always_on
---

# 🌐 CONFIGURACIÓN DE CONTEXT GRAPH (Variables del Proyecto / Workspace)
# ==============================================================================
# Si este archivo se usa a nivel LOCAL, especifica su ID directamente.
# Si se usa a nivel GLOBAL (~/.gemini/config/rules/), deja PROJECT_ID en "auto"
# para que el agente detecte automáticamente el proyecto activo mediante list_projects().
#
PROJECT_ID: "context_graph"
MCP_SERVER: "context_graph"
SERVER_URL: "http://localhost:8899"
# ==============================================================================


# 🌐 REGLA OPERATIVA: `context_graph` (Knowledge Graph & AST Accelerator)

Este workspace está integrado con el servidor FastMCP **`context_graph`**, un motor de indexación AST y grafo de dependencias para acelerar la comprensión arquitectónica y optimizar el consumo de tokens.

- **Servidor MCP**: `{{MCP_SERVER}}` (FastMCP / SSE en `{{SERVER_URL}}/sse`)
- **Visor Interactivo**: `{{SERVER_URL}}`
- **Identificador de Proyecto (`project_id`)**: `{{PROJECT_ID}}`

---

## 🎯 1. Resolución de `project_id`
- **Explícito**: Si `PROJECT_ID` tiene un valor asignado (distinto de `"auto"`), usarlo en todas las herramientas MCP.
- **Automático (`PROJECT_ID: "auto"`)**: Invocar `list_projects()`, comparar el nombre del directorio raíz del workspace con la lista de proyectos y asignar el `project_id` coincidente.

---

## ⚡ 2. Protocolo Zero-Read & Eficiencia de Tokens
Antes de abrir archivos completos de código:
1. **Descubrimiento**: Usar `get_project_summary(project_id)` o `query_graph_nodes(project_id, query="...", node_type="...")` para inspeccionar firmas, líneas AST (`start_line`, `end_line`) y docstrings.
2. **Extracción Quirúrgica**: Usar `get_code_slice(project_id, node_id, context_lines=0)` para obtener solo el fragmento relevante sin leer archivos enteros.
3. **Análisis de Impacto (Blast Radius)**: **Obligatorio** antes de refactorizar o modificar funciones, clases o modelos críticos: `get_impact_analysis(project_id, node_id, max_depth=2)` para evaluar dependientes directos y transitivos.
4. **Subgrafos Contextuales**: Usar `get_subgraph(project_id, focal_node_id, depth=1)` para entender el vecindario inmediato de un componente.

---

## 🔄 3. Sincronización y Git Multi-Rama
> [!IMPORTANT]
> - **Sincronización Git Incremental:** Usa `sync_project_graph(project_id, branch=None)` si cambiaste de commit o de rama en Git para actualizar el grafo automáticamente con el diff de commits.
> - **Reindexación Inmediata de Archivos Modificados:** Cada vez que crees, edites o elimines archivos en el workspace, sincroniza el grafo invocando inmediatamente `reindex_modified_files(project_id, file_paths=[...], branch=None)`.
> - **Soporte Multi-Rama:** Todas las herramientas aceptan `branch` opcional. Si se omite, se usa la rama activa de Git en el workspace.
> - **Política de Seguridad:** El MCP solo realiza operaciones incrementales seguras; la reconstrucción destructiva (`rebuild`) solo puede ejecutarse desde la Web UI.

