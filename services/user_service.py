
"""Manage user accounts using SQLite and Argon2 password hashing."""

import sqlite3
from pathlib import Path
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import (
    VerificationError,
    VerifyMismatchError,
)

from auth.permissions import Role
from models.user import User


PASSWORD_HASHER = PasswordHasher()


class UserService:
    """Manage persistent user identity records.

    Attributes:
        db_path (Path): SQLite database location.

    Functions:
        _connect: Open a configured SQLite connection.
        _initialize: Create authentication database tables.
        _to_user: Convert a database row into a public user.
        create_user: Create an account with a hashed password.
        get_user: Retrieve an account by ID.
        authenticate: Verify username and password.
        list_users: List accounts with optional role filtering.
        update_user: Update username or active status.
        reset_password: Replace an account password.
        delete_user: Delete an account.
    """

    def __init__(
        self,
        db_path: str | Path = "data/agents.db",
    ) -> None:
        """Initialize the user storage service.

        Args:
            db_path (str | Path): SQLite database path.

        Returns:
            None: Initializes the service.

        Raises:
            OSError: If the database directory cannot be created.
            sqlite3.Error: If database initialization fails.
        """
        self.db_path = Path(db_path)

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        """Open a configured SQLite connection.

        Args:
            None.

        Returns:
            sqlite3.Connection: Connection with named rows.

        Raises:
            sqlite3.Error: If the connection fails.
        """
        connection = sqlite3.connect(
            self.db_path,
            timeout=10,
        )

        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")

        return connection

    def _initialize(self) -> None:
        """Create authentication tables without altering agents.

        Args:
            None.

        Returns:
            None: Initializes missing tables.

        Raises:
            sqlite3.Error: If schema creation fails.
        """
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL
                        COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL
                        CHECK (
                            role IN (
                                'user',
                                'manager',
                                'admin'
                            )
                        ),
                    is_active INTEGER NOT NULL
                        DEFAULT 1
                        CHECK (is_active IN (0, 1)),
                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            connection.execute(
                """
                INSERT OR IGNORE INTO schema_migrations (
                    version
                )
                VALUES (1)
                """
            )

    @staticmethod
    def _to_user(row: sqlite3.Row) -> User:
        """Convert a database row into a public user.

        Args:
            row (sqlite3.Row): Retrieved database record.

        Returns:
            User: Public user model without credentials.

        Raises:
            ValueError: If the stored role is invalid.
        """
        return User(
            id=row["id"],
            username=row["username"],
            role=Role(row["role"]),
            is_active=bool(row["is_active"]),
        )

    def create_user(
        self,
        username: str,
        password: str,
        role: Role = Role.USER,
    ) -> User:
        """Create an account with an Argon2 password hash.

        Args:
            username (str): Unique login username.
            password (str): Plaintext password to hash.
            role (Role): Assigned application role.

        Returns:
            User: Newly created account.

        Raises:
            ValueError: If input is invalid or username exists.
            sqlite3.Error: If persistence fails.
        """
        username = username.strip()

        if not username or len(username) > 150:
            raise ValueError(
                "Username must contain 1 to 150 characters."
            )

        if not 12 <= len(password) <= 1024:
            raise ValueError(
                "Password must contain 12 to 1024 characters."
            )

        user_id = str(uuid4())

        password_hash = PASSWORD_HASHER.hash(password)

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        id,
                        username,
                        password_hash,
                        role
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        password_hash,
                        role.value,
                    ),
                )

        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Username already exists."
            ) from exc

        return User(
            id=user_id,
            username=username,
            role=role,
            is_active=True,
        )

    def get_user(
        self,
        user_id: str,
    ) -> User | None:
        """Retrieve a user by their identifier.

        Args:
            user_id (str): Unique user identifier.

        Returns:
            User | None: User if found, otherwise None.

        Raises:
            sqlite3.Error: If retrieval fails.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, username, role, is_active
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return self._to_user(row)

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> User | None:
        """Authenticate an active user using their password.

        Args:
            username (str): Submitted login username.
            password (str): Submitted plaintext password.

        Returns:
            User | None: Authenticated user or None.

        Raises:
            sqlite3.Error: If user lookup fails.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM users
                WHERE username = ?
                """,
                (username.strip(),),
            ).fetchone()

        if row is None:
            return None

        try:
            PASSWORD_HASHER.verify(
                row["password_hash"],
                password,
            )
        except (
            VerifyMismatchError,
            VerificationError,
        ):
            return None

        if not row["is_active"]:
            return None

        return self._to_user(row)

    def list_users(
        self,
        role: Role | None = None,
    ) -> list[User]:
        """Retrieve registered accounts with optional role filtering.

        Args:
            role (Role | None): Optional account role filter.

        Returns:
            list[User]: Matching accounts without password hashes.

        Raises:
            sqlite3.Error: If the database query fails.
        """
        query = """
            SELECT id, username, role, is_active
            FROM users
        """

        parameters: tuple[str, ...] = ()

        if role is not None:
            query += " WHERE role = ?"
            parameters = (role.value,)

        query += " ORDER BY username COLLATE NOCASE"

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [
            self._to_user(row)
            for row in rows
        ]

    def update_user(
        self,
        user_id: str,
        username: str | None = None,
        is_active: bool | None = None,
    ) -> User | None:
        """Update an account's username or active status.

        Args:
            user_id (str): Account identifier.
            username (str | None): Replacement username.
            is_active (bool | None): Replacement active status.

        Returns:
            User | None: Updated account or None if missing.

        Raises:
            ValueError: If username is invalid or duplicated.
            sqlite3.Error: If persistence fails.
        """
        if username is not None:
            username = username.strip()

            if not username or len(username) > 150:
                raise ValueError(
                    "Username must contain 1 to 150 characters."
                )

        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT id, username, role, is_active
                    FROM users
                    WHERE id = ?
                    """,
                    (user_id,),
                ).fetchone()

                if row is None:
                    return None

                next_username = (
                    username
                    if username is not None
                    else row["username"]
                )

                next_active = (
                    is_active
                    if is_active is not None
                    else bool(row["is_active"])
                )

                connection.execute(
                    """
                    UPDATE users
                    SET username = ?, is_active = ?
                    WHERE id = ?
                    """,
                    (
                        next_username,
                        int(next_active),
                        user_id,
                    ),
                )

        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Username already exists."
            ) from exc

        return self.get_user(user_id)

    def reset_password(
        self,
        user_id: str,
        new_password: str,
    ) -> bool:
        """Replace an account password with an Argon2 hash.

        Args:
            user_id (str): Account identifier.
            new_password (str): Replacement plaintext password.

        Returns:
            bool: True if the password was updated.

        Raises:
            ValueError: If the password is invalid.
            sqlite3.Error: If persistence fails.
        """
        if not 12 <= len(new_password) <= 1024:
            raise ValueError(
                "Password must contain 12 to 1024 characters."
            )

        password_hash = PASSWORD_HASHER.hash(
            new_password
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
                """,
                (
                    password_hash,
                    user_id,
                ),
            )

            return cursor.rowcount > 0

    def delete_user(
        self,
        user_id: str,
    ) -> bool:
        """Delete an account from persistent storage.

        Args:
            user_id (str): Account identifier.

        Returns:
            bool: True if the account was deleted.

        Raises:
            sqlite3.Error: If deletion fails.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM users
                WHERE id = ?
                """,
                (user_id,),
            )

            return cursor.rowcount > 0
