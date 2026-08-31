import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import PORT, HOST, DATA_PATH
from app.api.projects import router as projects_router
from app.api.graph_api import router as graph_router
from app.api.ingest_api import router as ingest_router
from app.mcp_server import mcp

app = FastAPI(title="local_graphs", description="Gestor y Visor Web de Grafos de Conocimiento Multi-Proyecto")

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

# Mount MCP SSE app onto /sse
mcp_app = mcp.sse_app()
app.mount("/sse", mcp_app)

# Static files for Web UI
web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web"))
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
