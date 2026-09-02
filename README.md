# 🌐 context_graph

Gestor y visor web interactivo de grafos de conocimiento multi-proyecto para desarrolladores y asistentes de IA (Antigravity & Claude).

---

## 🚀 Inicio Rápido (1 Clic)

1. **Configurar tus proyectos en `projects_config.json`:**
   Copia la plantilla y agrega las rutas absolutas de tus proyectos locales (personal, trabajo, etc.):
   ```bash
   cp projects_config.example.json projects_config.json
   ```

   *Ejemplo de `projects_config.json`:*
   ```json
   {
     "projects": [
       {
         "id": "mi_app_personal",
         "name": "Mi Proyecto Personal",
         "host_path": "/path/to/my_project"
       },
       {
         "id": "trabajo_backend",
         "name": "API de Pagos (Empresa)",
         "host_path": "/path/to/work_project"
       }
     ]
   }
   ```

2. **Levantar el Servicio:**
   - **Linux / macOS:**
     ```bash
     ./start.sh
     ```
   - **Windows (PowerShell):**
     ```powershell
     .\start.ps1
     ```

   *El script regenerará automáticamente el `docker-compose-volumes.yml` con los volúmenes de todos los proyectos configurados y levantará el contenedor.*

3. **Abrir la Interfaz Web:**
   Navega a [http://localhost:8899](http://localhost:8899).

---

## 🤖 Conexión con Asistentes de IA (MCP)

`context_graph` incluye un servidor MCP nativo expuesto vía SSE en `http://localhost:8899/sse`.

### Para Antigravity (`~/.gemini/config/mcp_config.json`):
```json
{
  "mcpServers": {
    "context_graph": {
      "serverUrl": "http://localhost:8899/sse"
    }
  }
}
```

### Para Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "context_graph": {
      "serverUrl": "http://localhost:8899/sse"
    }
  }
}
```

---

## 📁 Aislamiento de Proyectos
Cada proyecto vive en su propia subcarpeta dentro de `data/projects/{project_id}/` con su propio `graph.json` y `GRAPH_REPORT.md`. Los proyectos personales y profesionales nunca se mezclan ni comparten datos.

## 🛑 Detener el Servicio

- **Linux / macOS:**
  ```bash
  ./stop.sh
  ```
- **Windows (PowerShell):**
  ```powershell
  .\stop.ps1
  ```
