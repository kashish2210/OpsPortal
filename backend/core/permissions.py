"""Role-based access control.

The portal has four roles (Admin, Sales, Warehouse, Accounts). Rather than
scattering ``if user.role == ...`` through the views, each viewset declares the
roles allowed to read and to write via :class:`RolePermission`.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class RolePermission(BasePermission):
    """Grants access based on ``view.read_roles`` / ``view.write_roles``.

    Usage on a viewset::

        class ProductViewSet(ModelViewSet):
            permission_classes = [IsAuthenticated, RolePermission]
            read_roles = {Role.ADMIN, Role.SALES, Role.WAREHOUSE, Role.ACCOUNTS}
            write_roles = {Role.ADMIN, Role.WAREHOUSE}

    ``None`` (the default) means "any authenticated user". Admins and Django
    superusers always pass.
    """

    message = "Your role does not allow this action."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or getattr(user, "is_admin_role", False):
            return True

        roles = (
            getattr(view, "read_roles", None)
            if request.method in SAFE_METHODS
            else getattr(view, "write_roles", None)
        )
        if roles is None:
            return True
        return user.role in roles

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsAdminRole(BasePermission):
    """Only Admin-role users (or Django superusers)."""

    message = "Administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and (user.is_superuser or user.is_admin_role)
        )


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
