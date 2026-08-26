from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password: str) -> str:
    """Hash a plaintext password using Werkzeug security."""
    if not password:
        return ""
    return generate_password_hash(password)

def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verify a plaintext password against a stored hashed or legacy password."""
    if not stored_password or not provided_password:
        return False
    try:
        return check_password_hash(stored_password, provided_password)
    except Exception:
        # Fallback for plain-text backward compatibility
        return stored_password == provided_password
