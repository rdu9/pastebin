import secrets, hashlib
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

def generate_token() -> str:
    generated_token = secrets.token_urlsafe(32)
    return generated_token


def generate_hashed_token(token: str) -> str:
    generated_hash_token = hashlib.sha256(token.encode()).hexdigest()
    return generated_hash_token


def hash_password(password: str) -> str:
    hashed_password = ph.hash(password)
    return hashed_password
    

def verify_hashed_password(hashed_password: str, password: str) -> bool:
    try:
        return ph.verify(hashed_password, password)
    except VerifyMismatchError:
        return False
