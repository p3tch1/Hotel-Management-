from dataclasses import dataclass
from datetime import datetime, timezone
import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from hotel.db import collection

@dataclass
class Principal:
    id: str
    email: str
    role: str
    name: str = ''
    is_authenticated: bool = True

class BearerTokenAuthentication(BaseAuthentication):
    scheme_name = 'BearerAuth'
    def authenticate_header(self, request):
        return 'Bearer'

    def authenticate(self, request):
        raw = request.headers.get('Authorization', '')
        if not raw:
            return None
        if not raw.startswith('Bearer '):
            raise AuthenticationFailed('Use a Bearer access token.')
        try:
            claims = jwt.decode(raw[7:], settings.JWT_SECRET, algorithms=['HS256'])
            if collection('revoked_tokens').find_one({'jti': claims['jti']}):
                raise AuthenticationFailed('This access token has been logged out.')
            user = collection('users').find_one({'_id': __import__('bson').ObjectId(claims['sub']), 'active': True})
        except AuthenticationFailed:
            raise
        except Exception as exc:
            raise AuthenticationFailed('Access token is invalid or expired.') from exc
        if not user:
            raise AuthenticationFailed('Account is unavailable.')
        return Principal(str(user['_id']), user['email'], user['role'], user.get('name', '')), raw[7:]

def issue_token(user):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user['_id']), 'email': user['email'], 'role': user['role'], 'iat': now, 'exp': now.timestamp() + settings.JWT_LIFETIME_SECONDS, 'jti': __import__('uuid').uuid4().hex}, settings.JWT_SECRET, algorithm='HS256')
