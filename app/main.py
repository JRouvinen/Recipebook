"""ASGI application entrypoint: ``uvicorn app.main:app``."""

from .factory import create_app

app = create_app()
