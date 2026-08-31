import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", "8899"))
HOST = os.getenv("HOST", "0.0.0.0")
APP_ENV = os.getenv("APP_ENV", "production")
DATA_PATH = os.getenv("DATA_PATH", "/data/projects")
MAX_FILE_SIZE_KB = int(os.getenv("MAX_FILE_SIZE_KB", "1024"))

EXCLUDE_DIRS = set(
    filter(
        None,
        [d.strip() for d in os.getenv("EXCLUDE_DIRS", ".git,node_modules,.venv,dist,build,__pycache__,.next,.turbo,.cache,.graphify").split(",")]
    )
)

def get_configured_projects() -> List[Dict[str, Any]]:
    """
    Lee projects_config.json si existe.
    """
    config_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "projects_config.json"),
        "/app/projects_config.json",
        os.path.join(DATA_PATH, "projects_config.json")
    ]
    for cp in config_paths:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("projects", [])
            except Exception as e:
                print(f"Error reading {cp}: {e}")
    return []
