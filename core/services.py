from datetime import datetime, timedelta
from django.db import IntegrityError
from django.utils import timezone
from .models import Specialty, Doctor, Patient, Appointment


def list_specialties():
    return [{"name": s.name, "description": s.description} for s in Specialty.objects.all()]


def _free_slots(doctor, day):
    """All free slots (aware datetimes) for one doctor on one date."""
    now = timezone.now()
    taken = set(
        Appointment.objects.filter(doctor=doctor, start__date=day).values_list("start", flat=True)
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
    """Doctors of a specialty with their first free slots on `day` (a date)."""
    results = []
    doctors = Doctor.objects.filter(is_active=True, specialty__name__iexact=specialty_name)
    for doctor in doctors:
        slots = _free_slots(doctor, day)
        if slots:
            results.append({
                "doctor_id": doctor.id,
                "doctor": doctor.full_name,
                "slots": [s.strftime("%H:%M") for s in slots[:max_slots]],
            })
    return results


def book_appointment(doctor_id, day, time_str, patient_name, phone="", symptoms=""):
    """Books a slot. Returns a dict with ok=True/False and a message."""
    try:
        doctor = Doctor.objects.get(id=doctor_id, is_active=True)
    except Doctor.DoesNotExist:
        return {"ok": False, "message": "Doctor not found."}

    wanted = timezone.make_aware(
        datetime.combine(day, datetime.strptime(time_str, "%H:%M").time())
    )
    if wanted not in _free_slots(doctor, day):
        return {"ok": False, "message": "This slot is not available."}

    patient, _ = Patient.objects.get_or_create(full_name=patient_name, phone=phone)
    try:
        appt = Appointment.objects.create(
            patient=patient, doctor=doctor, start=wanted,
            symptoms_summary=symptoms, created_by_ai=True,
        )
    except IntegrityError:  # someone booked it a split second earlier
        return {"ok": False, "message": "This slot was just taken."}

    return {
        "ok": True,
        "appointment_id": appt.id,
        "message": f"Booked with Dr {doctor.full_name} on {day} at {time_str}.",
    }