from django.db import models


class Specialty(models.Model):
    name = models.CharField(max_length=100, unique=True)  # e.g. "Cardiologie"
    description = models.TextField(blank=True)  # helps the AI match symptoms

    def __str__(self):
        return self.name


class Doctor(models.Model):
    full_name = models.CharField(max_length=150)
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT, related_name="doctors")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Dr {self.full_name} ({self.specialty})"


class WorkingHours(models.Model):
    """Weekly availability: one row per doctor per working day."""
    DAYS = [(0, "Lundi"), (1, "Mardi"), (2, "Mercredi"), (3, "Jeudi"),
            (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche")]
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.IntegerField(choices=DAYS)
    start = models.TimeField()
    end = models.TimeField()
    slot_minutes = models.PositiveIntegerField(default=30)


class Patient(models.Model):
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.full_name


class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    start = models.DateTimeField()
    symptoms_summary = models.TextField(blank=True)  # what the AI heard
    created_by_ai = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["doctor", "start"], name="no_double_booking")
        ]