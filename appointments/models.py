from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Specialty(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(
        blank=True,
        help_text="Typical complaints for this specialty. Athena uses this to match symptoms.",
    )

    class Meta:
        verbose_name_plural = "specialties"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Doctor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="doctor_profile", limit_choices_to={"role": "doctor"},
    )
    # exactly ONE specialty, and it is required
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT, related_name="doctors")
    license_number = models.CharField("Numéro d'inscription à l'Ordre", max_length=50, unique=True)

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    # Refusal: the admin writes a reason and saves; the doctor sees it on his page.
    rejection_reason = models.TextField("Motif du refus", blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.user_id and self.user.role != "doctor":
            raise ValidationError({"user": "Cet utilisateur doit avoir le rôle Médecin."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def status(self):
        """pending (waiting for the admin), approved, or rejected."""
        if self.is_verified:
            return "approved"
        if self.rejected_at:
            return "rejected"
        return "pending"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def can_take_appointments(self):
        return self.is_active and self.is_verified

    def __str__(self):
        return f"Dr {self.full_name} ({self.specialty})"


class WorkingHours(models.Model):
    """Weekly availability: one row per doctor per working period."""
    DAYS = [(0, "Lundi"), (1, "Mardi"), (2, "Mercredi"), (3, "Jeudi"),
            (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche")]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.IntegerField("Jour", choices=DAYS)
    start = models.TimeField("Début")
    end = models.TimeField("Fin")
    slot_minutes = models.PositiveIntegerField("Durée d'un rendez-vous (min)", default=30)

    class Meta:
        verbose_name_plural = "working hours"
        ordering = ["doctor", "weekday", "start"]

    def clean(self):
        if self.start and self.end and self.end <= self.start:
            raise ValidationError("L'heure de fin doit être après l'heure de début.")
        if self.slot_minutes is not None and not (5 <= self.slot_minutes <= 240):
            raise ValidationError("La durée d'un rendez-vous doit être entre 5 et 240 minutes.")
        if self.doctor_id and self.weekday is not None and self.start and self.end:
            overlaps = WorkingHours.objects.filter(
                doctor_id=self.doctor_id, weekday=self.weekday,
                start__lt=self.end, end__gt=self.start,
            ).exclude(pk=self.pk)
            if overlaps.exists():
                raise ValidationError("Cette plage chevauche une plage existante ce jour-là.")

    def __str__(self):
        return f"{self.doctor} - {self.get_weekday_display()} {self.start:%H:%M}-{self.end:%H:%M}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Confirmé"
        CANCELLED = "cancelled", "Annulé"

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="appointments")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="appointments")
    start = models.DateTimeField()
    symptoms_summary = models.TextField(blank=True)  # what Athena heard / what the patient wrote
    created_by_ai = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.BOOKED)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    cancel_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["start"]
        constraints = [
            # a slot is taken only while the appointment is booked: a cancelled slot can be booked again
            models.UniqueConstraint(
                fields=["doctor", "start"], condition=models.Q(status="booked"), name="no_double_booking"
            )
        ]

    def __str__(self):
        return f"{self.patient} - {self.doctor} - {self.start:%d/%m/%Y %H:%M}"
