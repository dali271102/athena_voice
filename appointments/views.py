from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import WorkingHoursForm
from .models import Appointment, Doctor, Specialty, WorkingHours

DAYS_AHEAD = 14


def _patient_profile(request):
    profile = getattr(request.user, "patient_profile", None)
    if request.user.role != "patient" or profile is None:
        raise PermissionDenied
    return profile


@login_required
def book_specialty(request):
    """Step 1: the patient chooses a specialty."""
    _patient_profile(request)
    return render(request, "appointments/book_specialty.html", {
        "specialties": services.specialties_with_doctors(),
    })


@login_required
def book_slots(request, specialty_id):
    """Step 2: the patient chooses a day, a doctor and a time."""
    _patient_profile(request)
    specialty = get_object_or_404(Specialty, pk=specialty_id)
    today = timezone.localdate()
    days = [today + timedelta(days=i) for i in range(DAYS_AHEAD)]
    try:
        day = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        day = today
    if day < today or day > days[-1]:
        day = today
    doctors = services.get_available_doctors(specialty.name, day, max_slots=48)
    return render(request, "appointments/book_slots.html", {
        "specialty": specialty, "day": day, "days": days, "doctors": doctors,
    })


@login_required
@require_POST
def book_confirm(request):
    """Step 3: books the chosen slot for the logged-in patient."""
    profile = _patient_profile(request)
    try:
        doctor_id_text, time_str = request.POST["slot"].split("|")
        doctor_id = int(doctor_id_text)
        day = date.fromisoformat(request.POST["date"])
        datetime.strptime(time_str, "%H:%M")
    except (KeyError, ValueError):
        return HttpResponseBadRequest("Invalid request")

    today = timezone.localdate()
    if day < today or day > today + timedelta(days=DAYS_AHEAD - 1):
        return HttpResponseBadRequest("Invalid date")

    symptoms = request.POST.get("symptoms", "").strip()[:500]
    result = services.book_appointment(
        doctor_id, day, time_str, "", "", symptoms, patient=profile, by_ai=False
    )
    if result["ok"]:
        doctor = Doctor.objects.select_related("user", "specialty").get(pk=doctor_id)
        messages.success(
            request,
            f"Rendez-vous confirmé avec Dr {doctor.full_name} ({doctor.specialty}) "
            f"le {day:%d/%m/%Y} à {time_str}.",
        )
        return redirect("patient_dashboard")

    messages.error(request, "Ce créneau n'est plus disponible. Choisissez-en un autre.")
    doctor = Doctor.objects.filter(pk=doctor_id).first()
    if doctor:
        return redirect("book_slots", specialty_id=doctor.specialty_id)
    return redirect("book_specialty")


@login_required
@require_POST
def cancel_appointment(request, pk):
    """The patient or the doctor of an appointment can cancel it (nobody else, not even to see it exists)."""
    appt = get_object_or_404(Appointment.objects.select_related("patient", "doctor__user"), pk=pk)
    user = request.user
    patient_owner = user.role == "patient" and appt.patient.user_id == user.id
    doctor_owner = user.role == "doctor" and appt.doctor.user_id == user.id
    if not (patient_owner or doctor_owner):
        raise Http404
    result = services.cancel_appointment(appt, user, request.POST.get("reason", ""))
    if result["ok"]:
        messages.success(request, "Le rendez-vous a été annulé.")
    else:
        messages.error(request, result["message"])
    return redirect("patient_dashboard" if patient_owner else "doctor_dashboard")


def _doctor_profile(request):
    doctor = getattr(request.user, "doctor_profile", None)
    if request.user.role != "doctor" or doctor is None:
        raise PermissionDenied
    return doctor


@login_required
def doctor_hours(request):
    """A doctor manages his own weekly working hours."""
    doctor = _doctor_profile(request)
    form = WorkingHoursForm(request.POST or None, doctor=doctor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Horaire ajouté.")
        return redirect("doctor_hours")
    return render(request, "appointments/doctor_hours.html", {
        "doctor": doctor, "form": form, "hours": doctor.working_hours.all(),
    })


@login_required
@require_POST
def doctor_hours_delete(request, pk):
    doctor = _doctor_profile(request)
    wh = get_object_or_404(WorkingHours, pk=pk, doctor=doctor)  # only his own rows
    wh.delete()
    messages.success(request, "Horaire supprimé. Les rendez-vous déjà pris ne sont pas modifiés.")
    return redirect("doctor_hours")
