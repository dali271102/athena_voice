from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class CustomUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")  # createsuperuser makes an Administrateur
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):  # provisional: replace with your 7 RBAC roles
        ADMIN = "admin", "Administrateur"
        DOCTOR = "doctor", "Médecin"
        NURSE = "nurse", "Infirmier(ère)"
        RECEPTIONIST = "receptionist", "Réceptionniste"
        PHARMACIST = "pharmacist", "Pharmacien"
        LAB_TECH = "lab_tech", "Technicien de laboratoire"
        PATIENT = "patient", "Patient"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)

    objects = CustomUserManager()
