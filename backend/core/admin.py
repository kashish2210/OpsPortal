from django.contrib import admin

from .sequences import Sequence


@admin.register(Sequence)
class SequenceAdmin(admin.ModelAdmin):
    list_display = ("key", "last_value")
    search_fields = ("key",)
    readonly_fields = ("key",)

    def has_add_permission(self, request):
        # Counters are created on demand by the numbering helpers.
        return False
