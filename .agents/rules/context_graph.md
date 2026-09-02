# 🌐 REGLA DEL PROYECTO: `context_graph`

Este repositorio contiene el código fuente de **`context_graph`**: un gestor, indexador incremental AST y visor interactivo de grafos de conocimiento de código multi-proyecto, que expone un servidor **FastMCP** (SSE) para asistir a agentes de IA (Antigravity, Claude, etc.) optimizando drásticamente el consumo de tokens.

- **Nombre del servidor MCP**: `context_graph`
- **Transporte**: SSE en `http://localhost:8899/sse`
- **`project_id` de este repositorio**: **`context_graph`** (declarado en `projects_config.json`).
- **Visor Web**: `http://localhost:8899`

---

## 📌 Uso Operativo en este Workspace

- Al consultar o enriquecer el grafo de **este repositorio**, se debe utilizar siempre **`project_id: "context_graph"`**.
- Ejemplo: `query_graph_nodes(project_id="context_graph", query="...", node_type="Function")`.

---

## 🏛️ Arquitectura del Sistema

```
context_graph/
├── server/
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # FastAPI app, montaje estático Web UI y routers
│       ├── mcp_server.py        # Servidor FastMCP nativo expuesto en /sse
│       ├── config.py            # Gestión de config, variables de entorno y projects_config.json
│       ├── graph/
│       │   ├── model.py         # Modelos Pydantic (Node, Edge, GraphData)
│       │   └── storage.py       # Persistencia JSON atómica y aislamiento de proyectos
│       ├── api/                 # Endpoints REST (/api/projects, /api/tasks, /api/ingest, etc.)
│       └── ingestion/
│           ├── engine.py        # Motor incremental NetworkX, comunidades y generador de reportes
│           ├── walker.py        # Recorredor de directorios con exclusiones inteligentes
│           └── parsers/         # Parsers AST por lenguaje (Python AST, JS/TS, PHP, C#, etc.)
├── web/                         # Frontend Vanilla Modular (D3.js + Force-Graph)
│   ├── index.html
│   ├── css/ & js/
│   └── views/                   # Componentes modulares (canvas, summary, report, tasks, etc.)
├── data/projects/               # Persistencia de grafos aislados: {project_id}/graph.json
├── projects_config.json         # Fuente única de verdad de proyectos habilitados
├── start.ps1 / start.sh         # Generación dinámica de volúmenes y arranque Docker
└── stop.ps1 / stop.sh           # Detención limpia de contenedores
```

---

## 📌 Principios de Diseño y Reglas Obligatorias

### 1. `projects_config.json` es la Única Fuente de Verdad
- **Aislamiento Estricto**: Ningún endpoint de la API ni herramienta del servidor MCP debe exponer proyectos que no estén listados en `projects_config.json`.
- **Validación**: Siempre utilizar `is_project_configured(project_id)` antes de leer, modificar o reindexar un proyecto.

### 2. Optimización Radical de Tokens para Agentes MCP
- **Metadata Estructural Obligatoria**: Todos los parsers de código deben extraer metadatos enriquecidos en los nodos de funciones y clases:
  - `start_line` y `end_line` (para que los agentes usen `view_file(StartLine=..., EndLine=...)` con ahorro > 90%).
  - `signature` tipada, `parameters`, `return_type`, `visibility` (`public`/`private`/`protected`), `is_async`, `decorators` y `docstring`.
- **Zero-Read Principle**: El agente debe ser capaz de entender el contrato y dependencias de una función directamente desde el grafo sin abrir el archivo fuente.

### 3. Persistencia y Enriquecimiento de IA
- Los nodos y aristas creados o anotados por usuarios o IAs tienen `is_custom=True` y `origin="ai"` / `"manual"`.
- Las reindexaciones (incrementales o parciales) **NUNCA** deben sobrescribir ni borrar notas o conexiones que tengan `is_custom=True`.

### 4. Rendimiento en Frontend (Canvas 2D / D3 / Force-Graph)
- Para proyectos masivos (+2,000 nodos), el visor implementa **Viewport Culling** con streaming de vecindad (1-hop) para mantener 60 FPS.
- Mantener la interfaz limpia, moderna (tema oscuro, glassmorphism) y modular en `web/views/`.

### 5. Contenedor Docker y Despliegue
- El servicio corre en el contenedor `context_graph` en el puerto `8899` (`http://localhost:8899` y SSE en `http://localhost:8899/sse`).
- Al modificar código en `server/app/`, reiniciar el contenedor con `docker restart context_graph` para aplicar cambios de backend y MCP.
- Al agregar nuevos repositorios a `projects_config.json`, ejecutar `start.ps1` / `start.sh` para regenerar los puntos de montaje de volúmenes.

---

## 🧰 Herramientas MCP Expuestas por `context_graph`

| Herramienta MCP | Propósito |
| :--- | :--- |
| `list_projects()` | Lista proyectos autorizados en `projects_config.json`. |
| `get_project_summary(project_id)` | Devuelve `GRAPH_REPORT.md` con estadísticas y resumen arquitectónico. |
| `query_graph_nodes(project_id, query, node_type)` | Búsqueda rápida de nodos con metadata de líneas y firmas. |
| `get_node_connections(project_id, node_id)` | Devuelve dependencias entrantes y salientes de un nodo. |
| `update_node_context(project_id, node_id, description)` | Enriquece con notas técnicas persistentes un nodo (`origin="ai"`). |
| `add_custom_connection(project_id, source, target, relation)` | Crea enlaces relacionales persistentes entre nodos. |
| `reindex_modified_files(project_id, file_paths)` | Reindexa parcialmente archivos específicos tras una edición. |
