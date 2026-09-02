import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from app.config import PORT, HOST, DATA_PATH
from app.api.projects import router as projects_router
from app.api.graph_api import router as graph_router
from app.api.ingest_api import router as ingest_router
from app.api.tasks_api import router as tasks_router
from app.mcp_server import mcp

app = FastAPI(
    title="context_graph",
    version="1.1.0",
    description="Gestor y Visor Web de Grafos de Conocimiento Multi-Proyecto"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(projects_router)
app.include_router(graph_router)
app.include_router(ingest_router)
app.include_router(tasks_router)

# Static files for Web UI
web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web"))
if os.path.exists(web_dir):
    for folder in ["css", "js", "views"]:
        fpath = os.path.join(web_dir, folder)
        if os.path.exists(fpath):
            app.mount(f"/{folder}", StaticFiles(directory=fpath), name=folder)

    @app.get("/")
    async def get_index():
        index_file = os.path.join(web_dir, "index.html")
        return FileResponse(index_file)

import contextlib

# Montar los manejadores ASGI nativos de FastMCP (SSE y Streamable HTTP)
mcp_sse_app = mcp.sse_app()
mcp_http_app = mcp.streamable_http_app()

@contextlib.asynccontextmanager
async def lifespan(app_instance: FastAPI):
    async with mcp.session_manager.run():
        yield

app.router.lifespan_context = lifespan

app.routes.extend(mcp_sse_app.routes)
app.routes.extend(mcp_http_app.routes)

# Compatibilidad con clientes MCP (Antigravity/Claude) que envían POST directo al endpoint /sse
for route in mcp_http_app.routes:
    if getattr(route, "path", None) == "/mcp":
        from starlette.routing import Route
        app.routes.append(Route("/sse", endpoint=route.endpoint, methods=["POST"]))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)

