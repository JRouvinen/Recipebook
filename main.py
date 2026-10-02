"""Local development entrypoint.

Run with::

    python main.py

or, for the standard ASGI command::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
