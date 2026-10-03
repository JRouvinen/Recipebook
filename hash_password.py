"""Generate a password hash for ``RECIPEBOOK_AUTH_PASSWORD_HASH``.

Usage::

    .venv/bin/python hash_password.py            # prompts for a password
    .venv/bin/python hash_password.py 'my pass'  # hashes the argument
"""

from __future__ import annotations

import getpass
import sys

from app.security import hash_password


def main() -> None:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match.", file=sys.stderr)
            raise SystemExit(1)
    if not password:
        print("Password must not be empty.", file=sys.stderr)
        raise SystemExit(1)
    print(hash_password(password))


if __name__ == "__main__":
    main()
