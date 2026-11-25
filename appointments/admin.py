from django.contrib import admin
from django.utils import timezone

from .models import Appointment, Doctor, Specialty, WorkingHours


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


class WorkingHoursInline(admin.TabularInline):
    model = WorkingHours
    extra = 1


class DoctorStatusFilter(admin.SimpleListFilter):
    title = "statut"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [("pending", "En attente"), ("approved", "Accepté"), ("rejected", "Refusé")]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "approved":
            return queryset.filter(is_verified=True)
        if value == "rejected":
            return queryset.filter(is_verified=False, rejected_at__isnull=False)
        if value == "pending":
            return queryset.filter(is_verified=False, rejected_at__isnull=True)
        return queryset


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "specialty", "license_number", "status_label", "is_active")
    list_filter = (DoctorStatusFilter, "specialty", "is_active")
    search_fields = ("user__first_name", "user__last_name", "license_number")
    # verification fields can only be changed through the actions below; a refusal = write a reason and save
    readonly_fields = ("is_verified", "verified_at", "verified_by", "rejected_at")
    inlines = [WorkingHoursInline]
    actions = ["verify_doctors"]

    @admin.display(description="Statut")
    def status_label(self, obj):
        return {"approved": "✅ Accepté", "rejected": "❌ Refusé", "pending": "⏳ En attente"}[obj.status]

    @admin.action(description="Accepter (vérifier) les médecins sélectionnés")
    def verify_doctors(self, request, queryset):
        if not (request.user.is_superuser or request.user.role == "admin"):
            self.message_user(request, "Seul un administrateur peut accepter un médecin.", level="error")
            return
        n = queryset.update(
            is_verified=True, verified_at=timezone.now(), verified_by=request.user,
            rejected_at=None, rejection_reason="",
        )
        self.message_user(request, f"{n} médecin(s) accepté(s).")

    def save_model(self, request, obj, form, change):
        if obj.is_verified:
            obj.rejected_at = None
        elif obj.rejection_reason.strip():
            obj.rejected_at = obj.rejected_at or timezone.now()
        else:
            obj.rejected_at = None
        super().save_model(request, obj, form, change)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("start", "doctor", "patient", "status", "created_by_ai")
    list_filter = ("status", "doctor__specialty", "created_by_ai")
    search_fields = ("patient__full_name", "patient__phone")
