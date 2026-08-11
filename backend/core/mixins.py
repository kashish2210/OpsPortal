"""Reusable viewset mixins."""


class AuditedModelMixin:
    """Stamps ``created_by`` / ``updated_by`` from the authenticated user."""

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
