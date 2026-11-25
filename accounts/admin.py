from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Rôle", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Rôle", {"fields": ("role",)}),)
    list_display = ("username", "get_full_name", "role", "is_active")
    list_filter = ("role", "is_active")
