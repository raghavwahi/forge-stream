"""Bootstrap (or rotate) the ForgeStream admin user.

Usage
-----
    DATABASE_URL=postgresql://user:pass@host:5432/db python -m scripts.init_admin

Environment variables
---------------------
    DATABASE_URL  – PostgreSQL connection string (required).
    ADMIN_EMAIL   – Admin e-mail address (default: admin@forgestream.local).

Behaviour
---------
* If no admin user exists → creates one with a random secure password.
* If an admin user already exists → rotates its password.
* The generated password is printed to stdout **once**.
"""

from __future__ import annotations

import os
import secrets
import string
import sys

import bcrypt
import psycopg2  # type: ignore[import-untyped]


def _generate_password(length: int = 24) -> str:
    """Return a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def init_admin(database_url: str, admin_email: str) -> str:
    """Create or rotate the admin user and return the new password."""
    password = _generate_password()
    password_hash = _hash_password(password)

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            # Look up user by email regardless of role
            cur.execute(
                "SELECT id, role FROM users WHERE email = %s",
                (admin_email,),
            )
            row = cur.fetchone()

            if row is None:
                # No user with this email – create a new admin
                cur.execute(
                    """
                    INSERT INTO users (email, display_name, role, password_hash)
                    VALUES (%s, %s, 'admin', %s)
                    """,
                    (admin_email, "Admin", password_hash),
                )
                action = "created"
            else:
                # User exists – promote to admin (if needed) and rotate password
                cur.execute(
                    """
                    UPDATE users
                       SET password_hash = %s,
                           role          = 'admin',
                           updated_at    = now()
                     WHERE id = %s
                    """,
                    (password_hash, row[0]),
                )
                existing_role = row[1]
                action = (
                    "promoted to admin and password rotated"
                    if existing_role != "admin"
                    else "rotated"
                )

    print(f"Admin user {action}: {admin_email}")
    return password


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is required.", file=sys.stderr)
        sys.exit(1)

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@forgestream.local")

    password = init_admin(database_url, admin_email)
    print(f"Password: {password}")
    print("Store this password securely – it will not be shown again.")


if __name__ == "__main__":
    main()
