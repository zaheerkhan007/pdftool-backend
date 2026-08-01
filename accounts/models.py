from django.contrib.auth.models import User
from django.db import models


class ToolUsage(models.Model):
    """One row per tool run. Powers the dashboard analytics."""
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="usages"
    )
    tool = models.CharField(max_length=50)
    file_count = models.PositiveIntegerField(default=1)
    input_bytes = models.BigIntegerField(default=0)
    output_bytes = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tool} @ {self.created_at:%Y-%m-%d %H:%M}"
