"""Gap-free, race-safe document numbering.

``MAX(id) + 1`` breaks the moment two sales users save a challan at the same
instant. This keeps one counter row per sequence key and locks it with
``SELECT ... FOR UPDATE`` while it is incremented, so concurrent requests
serialise on the counter instead of colliding on a unique index.
"""

from django.db import models, transaction


class Sequence(models.Model):
    """One auto-numbering counter (e.g. ``customer``, ``challan:202608``)."""

    key = models.CharField(max_length=64, unique=True)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "sequence"
        verbose_name_plural = "sequences"

    def __str__(self):
        return f"{self.key} = {self.last_value}"

    @classmethod
    def next_number(cls, key):
        """Return the next integer for ``key`` (atomic)."""
        with transaction.atomic():
            counter, _created = cls.objects.select_for_update().get_or_create(key=key)
            counter.last_value = models.F("last_value") + 1
            counter.save(update_fields=["last_value"])
            counter.refresh_from_db(fields=["last_value"])
            return counter.last_value

    @classmethod
    def next_formatted(cls, key, prefix="", padding=5):
        """Return the next value rendered as ``<prefix><zero-padded number>``."""
        return f"{prefix}{cls.next_number(key):0{padding}d}"
