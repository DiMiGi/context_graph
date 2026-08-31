import os
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
