"""Encrypt sensitive guest fields before they are stored in MongoDB."""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PREFIX = 'enc:v1:'
SENSITIVE_GUEST_FIELDS = ('address', 'idProofNo')


def _fernet():
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '').strip()
    if not key:
        raise ImproperlyConfigured(
            'Set FIELD_ENCRYPTION_KEY in backend/.env. Generate one with '
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())".'
        )
    try:
        return Fernet(key.encode('ascii'))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured('FIELD_ENCRYPTION_KEY must be a valid Fernet key.') from exc


def encrypt_value(value):
    if value is None or value == '' or (isinstance(value, str) and value.startswith(PREFIX)):
        return value
    return PREFIX + _fernet().encrypt(str(value).encode('utf-8')).decode('ascii')


def decrypt_value(value):
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value  # Keep legacy plaintext records readable until migrated.
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode('ascii')).decode('utf-8')
    except (InvalidToken, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured(
            'Cannot decrypt guest data. Check that FIELD_ENCRYPTION_KEY matches the key used to encrypt it.'
        ) from exc


def protect_guest_fields(record):
    protected = dict(record)
    for field in SENSITIVE_GUEST_FIELDS:
        if field in protected:
            protected[field] = encrypt_value(protected[field])
    return protected
