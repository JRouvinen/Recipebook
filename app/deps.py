"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import Settings


def get_db(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.db.session()
    try:
        yield session
    finally:
        session.close()


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
