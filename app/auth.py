"""Authentication hook.

Version 1 has no users: every request acts as a single local user. All routes
depend on :func:`get_current_user`, so adding real authentication later means
changing this module only (e.g. read a session cookie, resolve a user, redirect
to a login page).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request


@dataclass(frozen=True)
class User:
    id: int | None = None
    username: str = "local"
    authenticated: bool = False

    @property
    def display_name(self) -> str:
        return self.username


async def get_current_user(request: Request) -> User:  # noqa: ARG001 - kept for future auth
    """Return the acting user. Currently always the anonymous local user."""
    return User()


CurrentUser = Annotated[User, Depends(get_current_user)]
