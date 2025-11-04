import os
import sys

# Garante que o diretório raiz do projeto esteja no sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import app.main  # noqa: F401
    print("IMPORT_OK")
except Exception as e:
    print("IMPORT_FAIL:", repr(e))
    raise
