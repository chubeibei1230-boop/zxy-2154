from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user and user.get("role") == "admin"


class IsFieldStaff(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user and user.get("role") == "field_staff"


class IsObserver(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user and user.get("role") == "observer"


class IsAdminOrFieldStaff(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user and user.get("role") in ("admin", "field_staff")


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return user.get("role") == "admin"


class CanWriteOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return user.get("role") in ("admin", "field_staff")
