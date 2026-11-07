import os
from pathlib import Path
from dotenv import load_dotenv

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# On Vercel / serverless platforms, deployment root is read-only.
# We route data storage to /tmp/data when running on Vercel.
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))
if IS_VERCEL:
    DATA_DIR = Path("/tmp/data")
else:
    DATA_DIR = BASE_DIR / "data"

PROJECTS_DIR = DATA_DIR / "projects"
PROJECTS_FILE = DATA_DIR / "projects.json"

# Load environment variables
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Ensure data directories exist
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # In Vercel, copy any existing project template data from read-only bundle to /tmp
    if IS_VERCEL and (BASE_DIR / "data").exists():
        import shutil
        seed_dir = BASE_DIR / "data"
        for item in seed_dir.iterdir():
            dest = DATA_DIR / item.name
            if not dest.exists():
                try:
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    elif item.is_file():
                        shutil.copy2(item, dest)
                except Exception:
                    pass
except Exception as e:
    print(f"Directory initialization notice: {e}")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY and "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# Default RAG settings
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_TOP_K = 4

# Supported LLM providers
PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "models": ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest"],
        "default_model": "gemini-3.5-flash-lite",
        "requires_key": True,
        "key_env": "GEMINI_API_KEY",
    },
    "groq": {
        "name": "Groq (Ultra-Fast Llama 3)",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "default_model": "llama-3.3-70b-versatile",
        "requires_key": True,
        "key_env": "GROQ_API_KEY",
    },
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        "default_model": "gpt-4o-mini",
        "requires_key": True,
        "key_env": "OPENAI_API_KEY",
    },
    "offline": {
        "name": "Built-in Local Offline Engine",
        "models": ["local-synthesis-v1"],
        "default_model": "local-synthesis-v1",
        "requires_key": False,
        "key_env": None,
    }
}
