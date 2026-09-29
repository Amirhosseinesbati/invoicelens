"""Create a customer workspace and first admin in CONNECTED mode."""

import argparse
import getpass
import re

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .models import User, Workspace
from .security import password_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="ASCII workspace slug")
    parser.add_argument("--name", required=True, help="Customer organization name")
    parser.add_argument("--email", required=True, help="First admin email")
    args = parser.parse_args()
    if get_settings().mode != "CONNECTED":
        raise SystemExit("Bootstrap requires INVOICELENS_MODE=CONNECTED")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,47}", args.workspace):
        raise SystemExit("Workspace must be a lowercase slug of 3–48 characters")
    password = getpass.getpass("Admin password: ")
    if len(password) < 12:
        raise SystemExit("Use at least 12 password characters")
    with SessionLocal() as db:
        if db.get(Workspace, args.workspace) or db.scalar(
            select(User).where(User.email == args.email.casefold())
        ):
            raise SystemExit("Workspace or email already exists")
        db.add(Workspace(id=args.workspace, name=args.name, is_demo=False))
        db.add(
            User(
                workspace_id=args.workspace,
                email=args.email.casefold(),
                role="admin",
                password_hash=password_hash.hash(password),
            )
        )
        db.commit()
    print(f"Created workspace {args.workspace} and admin {args.email.casefold()}")


if __name__ == "__main__":
    main()
