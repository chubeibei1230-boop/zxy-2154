from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from . import storage


class InMemoryUser:
    def __init__(self, data):
        self._data = data
        for key, value in data.items():
            setattr(self, key, value)

    @property
    def is_authenticated(self):
        return True

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def __repr__(self):
        return f"InMemoryUser({self._data.get('username', 'unknown')})"


class InMemoryTokenAuthentication(BaseAuthentication):
    keyword = 'Token'

    def authenticate(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth:
            return None
        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != 'token':
            return None
        token = parts[1]
        user_data = storage.get_user_by_token(token)
        if not user_data:
            raise AuthenticationFailed('无效的认证令牌')
        user = InMemoryUser(user_data)
        return (user, token)

    def authenticate_header(self, request):
        return 'Token'
