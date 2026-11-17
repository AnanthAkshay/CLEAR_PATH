"""ClearPath Streamlit Dashboard entry point.

Direct alias executing the root multipage application at streamlit_app.py.
Maintains full backward compatibility with `streamlit run clearpath/dashboard/app.py`.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_ENTRY_POINT = _ROOT / "streamlit_app.py"

if __name__ == "__main__" or True:
    runpy.run_path(str(_ENTRY_POINT), run_name="__main__")
