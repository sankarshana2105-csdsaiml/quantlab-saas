from .repository import DuplicateUserRecord, RecordNotFound, RepositoryError, SQLAlchemyRepository, UserRecord
from .security import DUMMY_PASSWORD_HASH, create_access_token, decode_access_token, hash_password, verify_password


class DuplicateEmail(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class AuthServiceError(Exception):
    pass


class AuthService:
    def __init__(self, repository: SQLAlchemyRepository):
        self.repository = repository

    def register(self, email: str, password: str) -> UserRecord:
        try:
            return self.repository.create_user(email.strip().lower(), hash_password(password))
        except DuplicateUserRecord:
            raise DuplicateEmail("Email is already registered") from None
        except RepositoryError:
            raise AuthServiceError("Authentication service unavailable") from None

    def login(self, email: str, password: str) -> str:
        try:
            user = self.repository.find_user_by_email(email.strip().lower())
        except RepositoryError:
            raise AuthServiceError("Authentication service unavailable") from None
        valid = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)
        if user is None or not valid:
            raise InvalidCredentials("Invalid email or password")
        return create_access_token(user.id)

    def current_user(self, token: str) -> UserRecord:
        try:
            identifier = decode_access_token(token)
            return self.repository.get_user(identifier)
        except (ValueError, RecordNotFound):
            raise InvalidCredentials("Invalid or expired token") from None
        except RepositoryError:
            raise AuthServiceError("Authentication service unavailable") from None
