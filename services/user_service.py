
"""Manage user accounts using PostgreSQL and Argon2 password hashing."""

from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from auth.permissions import Role
from database.connection import SessionLocal
from database.models import UserModel
from models.user import User


PASSWORD_HASHER = PasswordHasher()


class UserService:
    """Manage persistent user identity records.

    Attributes:
        session_factory (sessionmaker): PostgreSQL session factory.

    Functions:
        _to_user: Convert a database record into a public user.
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
        db_path: str | None = None,
        session_factory: sessionmaker = SessionLocal,
    ) -> None:
        """Initialize PostgreSQL user storage.

        Args:
            db_path (str | None): Deprecated SQLite argument, retained
                temporarily for compatibility with existing callers.
            session_factory (sessionmaker): SQLAlchemy session factory.

        Returns:
            None: Initializes the service.

        Raises:
            None.
        """
        self.session_factory = session_factory

    @staticmethod
    def _to_user(record: UserModel) -> User:
        """Convert a database record into a public user.

        Args:
            record (UserModel): Stored PostgreSQL user record.

        Returns:
            User: Public user model without password credentials.

        Raises:
            ValueError: If the stored role is invalid.
        """
        return User(
            id=record.id,
            username=record.username,
            role=Role(record.role),
            is_active=record.is_active,
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
            SQLAlchemyError: If persistence fails.
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

        record = UserModel(
            id=str(uuid4()),
            username=username,
            password_hash=PASSWORD_HASHER.hash(password),
            role=role.value,
            is_active=True,
        )

        try:
            with self.session_factory.begin() as session:
                session.add(record)
                session.flush()

                user = self._to_user(record)

        except IntegrityError as exc:
            raise ValueError(
                "Username already exists."
            ) from exc

        return user

    def get_user(self, user_id: str) -> User | None:
        """Retrieve a user by identifier.

        Args:
            user_id (str): Unique user identifier.

        Returns:
            User | None: Matching account or None.

        Raises:
            SQLAlchemyError: If retrieval fails.
        """
        with self.session_factory() as session:
            record = session.get(UserModel, user_id)

            return self._to_user(record) if record else None

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> User | None:
        """Authenticate an active user using Argon2.

        Args:
            username (str): Submitted login username.
            password (str): Submitted plaintext password.

        Returns:
            User | None: Authenticated account or None.

        Raises:
            SQLAlchemyError: If user lookup fails.
        """
        with self.session_factory() as session:
            record = session.scalar(
                select(UserModel).where(
                    func.lower(UserModel.username)
                    == username.strip().lower()
                )
            )

            if record is None:
                return None

            try:
                PASSWORD_HASHER.verify(
                    record.password_hash,
                    password,
                )
            except (
                VerifyMismatchError,
                VerificationError,
            ):
                return None

            if not record.is_active:
                return None

            return self._to_user(record)

    def list_users(
        self,
        role: Role | None = None,
    ) -> list[User]:
        """List registered accounts with optional role filtering.

        Args:
            role (Role | None): Optional account role filter.

        Returns:
            list[User]: Matching public user records.

        Raises:
            SQLAlchemyError: If retrieval fails.
        """
        statement = select(UserModel)

        if role is not None:
            statement = statement.where(
                UserModel.role == role.value
            )

        statement = statement.order_by(
            func.lower(UserModel.username)
        )

        with self.session_factory() as session:
            records = session.scalars(statement).all()

            return [
                self._to_user(record)
                for record in records
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
            SQLAlchemyError: If persistence fails.
        """
        if username is not None:
            username = username.strip()

            if not username or len(username) > 150:
                raise ValueError(
                    "Username must contain 1 to 150 characters."
                )

        try:
            with self.session_factory.begin() as session:
                record = session.get(UserModel, user_id)

                if record is None:
                    return None

                if username is not None:
                    record.username = username

                if is_active is not None:
                    record.is_active = is_active

                session.flush()
                user = self._to_user(record)

        except IntegrityError as exc:
            raise ValueError(
                "Username already exists."
            ) from exc

        return user

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
            SQLAlchemyError: If persistence fails.
        """
        if not 12 <= len(new_password) <= 1024:
            raise ValueError(
                "Password must contain 12 to 1024 characters."
            )

        password_hash = PASSWORD_HASHER.hash(new_password)

        with self.session_factory.begin() as session:
            record = session.get(UserModel, user_id)

            if record is None:
                return False

            record.password_hash = password_hash

            return True

    def delete_user(self, user_id: str) -> bool:
        """Delete an account from PostgreSQL.

        Args:
            user_id (str): Account identifier.

        Returns:
            bool: True if the account was deleted.

        Raises:
            SQLAlchemyError: If deletion fails.
        """
        with self.session_factory.begin() as session:
            record = session.get(UserModel, user_id)

            if record is None:
                return False

            session.delete(record)

            return True
