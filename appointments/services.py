from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from patients.models import Patient

from .models import Appointment, Doctor, Specialty


def specialties_with_doctors():
    """Specialties that have at least one verified, active doctor."""
    return Specialty.objects.filter(
        doctors__is_active=True, doctors__is_verified=True
    ).distinct()


def list_specialties():
    return [{"name": s.name, "description": s.description} for s in specialties_with_doctors()]


def _free_slots(doctor, day):
    """All free slots (aware datetimes) for one doctor on one date."""
    now = timezone.now()
    taken = set(
        Appointment.objects.filter(
            doctor=doctor, start__date=day, status=Appointment.Status.BOOKED
        ).values_list("start", flat=True)
    )
    slots = []
    for wh in doctor.working_hours.filter(weekday=day.weekday()):
        current = datetime.combine(day, wh.start)
        end = datetime.combine(day, wh.end)
        step = timedelta(minutes=wh.slot_minutes)
        while current + step <= end:
            aware = timezone.make_aware(current)
            if aware > now and aware not in taken:
                slots.append(aware)
            current += step
    return sorted(slots)


def get_available_doctors(specialty_name, day, max_slots=5):
    """Verified, active doctors of a specialty with their first free slots on `day` (a date)."""
    results = []
    doctors = Doctor.objects.filter(
        is_active=True, is_verified=True, specialty__name__iexact=specialty_name
    ).select_related("user", "specialty")
    for doctor in doctors:
        slots = _free_slots(doctor, day)
        if slots:
            results.append({
                "doctor_id": doctor.id,
                "doctor": doctor.full_name,
                "slots": [s.strftime("%H:%M") for s in slots[:max_slots]],
            })
    return results


def book_appointment(doctor_id, day, time_str, patient_name, phone="", symptoms="", patient=None, by_ai=True):
    """Books a slot. Returns a dict with ok=True/False and a message.
    `patient` = a logged-in Patient; when given, the name is not required.
    `by_ai` = True when Athena booked it, False when the patient booked it himself."""
    name = (patient_name or "").strip()
    if patient is None and (
        len(name) < 3 or name.lower() in {"patient", "unknown", "inconnu", "test", "n/a", "none"}
    ):
        return {"ok": False, "message": "The patient's full name is required. Ask the patient for their full name."}

    try:
        doctor = Doctor.objects.select_related("user").get(id=doctor_id, is_active=True, is_verified=True)
    except Doctor.DoesNotExist:
        return {"ok": False, "message": "Doctor not found."}

    try:
        wanted = timezone.make_aware(
            datetime.combine(day, datetime.strptime(time_str, "%H:%M").time())
        )
    except ValueError:
        return {"ok": False, "message": "Invalid time."}
    if wanted not in _free_slots(doctor, day):
        return {"ok": False, "message": "This slot is not available."}

    if patient is None:
        patient, _ = Patient.objects.get_or_create(full_name=name, phone=phone)
    elif phone and not patient.phone:
        patient.phone = phone
        patient.save(update_fields=["phone"])
    try:
        with transaction.atomic():
            appt = Appointment.objects.create(
                patient=patient, doctor=doctor, start=wanted,
                symptoms_summary=symptoms, created_by_ai=by_ai,
            )
    except IntegrityError:  # someone booked it a split second earlier
        return {"ok": False, "message": "This slot was just taken."}

    return {
        "ok": True,
        "appointment_id": appt.id,
        "message": f"Booked with Dr {doctor.full_name} on {day} at {time_str}.",
    }


def cancel_appointment(appointment, user, reason=""):
    """Cancels a future, booked appointment. The slot becomes free again."""
    if appointment.status != Appointment.Status.BOOKED:
        return {"ok": False, "message": "Ce rendez-vous est déjà annulé."}
    if appointment.start <= timezone.now():
        return {"ok": False, "message": "Ce rendez-vous est déjà passé."}
    appointment.status = Appointment.Status.CANCELLED
    appointment.cancelled_at = timezone.now()
    appointment.cancelled_by = user
    appointment.cancel_reason = (reason or "").strip()[:300]
    appointment.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancel_reason"])
    return {"ok": True, "message": "Rendez-vous annulé."}
