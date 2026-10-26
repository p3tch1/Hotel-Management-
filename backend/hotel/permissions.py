from rest_framework.permissions import BasePermission

class RolePermission(BasePermission):
    roles = set()
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, 'is_authenticated', False) and request.user.role in self.roles)

class IsStaff(RolePermission): roles = {'staff', 'manager'}
class IsManager(RolePermission): roles = {'manager'}
class IsGuest(RolePermission): roles = {'guest'}
class IsStaffOrGuest(RolePermission): roles = {'guest', 'staff', 'manager'}
