"""
Create (or promote) an administrator account.

Public signup always creates a plain `user`, so this script is the only way an
admin comes into existence — deliberate and auditable, rather than "whoever
registers first gets the keys".

Usage, from the backend/ directory:

    ./.venv/bin/python -m scripts.create_admin admin@example.com
    ./.venv/bin/python -m scripts.create_admin admin@example.com --password s3cret

With no --password, one is read from the terminal without echoing.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.security import MAX_PASSWORD_BYTES, hash_password  # noqa: E402
from app.auth.service import get_user_by_email  # noqa: E402
from app.db import AsyncSessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


async def create_admin(email: str, password: str) -> str:
    async with AsyncSessionLocal() as db:
        existing = await get_user_by_email(db, email)
        if existing is not None:
            if existing.role == UserRole.ADMIN:
                return f"{existing.email} is already an administrator."
            existing.role = UserRole.ADMIN
            await db.commit()
            return f"Promoted existing account {existing.email} to administrator."

        db.add(
            User(
                email=email.strip().lower(),
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        await db.commit()
        return f"Created administrator {email.strip().lower()}."


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote a DeployForge admin.")
    parser.add_argument("email")
    parser.add_argument("--password", help="prompted for if omitted")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if len(password.encode("utf-8")) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        print(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.", file=sys.stderr)
        return 1

    print(asyncio.run(create_admin(args.email, password)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
