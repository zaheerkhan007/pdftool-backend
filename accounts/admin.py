from django.contrib import admin

from .models import ToolUsage


@admin.register(ToolUsage)
class ToolUsageAdmin(admin.ModelAdmin):
    list_display = ("tool", "user", "file_count", "created_at")
    list_filter = ("tool", "created_at")
