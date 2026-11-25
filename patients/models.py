from django.conf import settings
from django.db import models


class Patient(models.Model):
    # Optional link to a login account. Patients booked by phone or by a guest
    # conversation with Athena have no account (user is empty).
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="patient_profile",
    )
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name
