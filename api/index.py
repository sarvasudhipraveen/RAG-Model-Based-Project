import sys
from pathlib import Path

# Add project root directory to sys.path so 'app' module can be imported
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.main import app

# Vercel looks for the ASGI application callable named 'app'
__all__ = ["app"]

