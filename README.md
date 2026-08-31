# 🌐 local_graphs

Gestor y visor web interactivo de grafos de conocimiento multi-proyecto para desarrolladores y asistentes de IA (Antigravity & Claude).

---

## 🚀 Inicio Rápido con Docker

1. **Configurar el entorno:**
   ```bash
   cp .env.example .env
   ```

2. **Construir y levantar el contenedor:**
   ```bash
   docker compose up -d --build
   ```

3. **Abrir la Interfaz Web:**
   Navega a [http://localhost:8899](http://localhost:8899).

---

## 🤖 Conexión con Asistentes de IA (MCP)

`local_graphs` incluye un servidor MCP nativo expuesto vía SSE en `http://localhost:8899/sse`.

### Para Antigravity (`~/.gemini/config/mcp_config.json`):
```json
{
  "mcpServers": {
    "local_graphs": {
      "serverUrl": "http://localhost:8899/sse"
    }
  }
}
```

### Para Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "local_graphs": {
      "serverUrl": "http://localhost:8899/sse"
    }
  }
}
```

---

## 📁 Aislamiento de Proyectos
Cada proyecto vive en su propia subcarpeta dentro de `data/projects/{project_id}/` con su propio `graph.json` y `GRAPH_REPORT.md`. Los proyectos personales y profesionales nunca se mezclan.
