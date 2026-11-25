from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone

from appointments.models import Appointment

from .forms import DoctorSignUpForm, PatientSignUpForm
from .models import User


def _signup(request, form_class, template):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return render(request, template, {"form": form})


def patient_signup(request):
    return _signup(request, PatientSignUpForm, "accounts/signup_patient.html")


def doctor_signup(request):
    return _signup(request, DoctorSignUpForm, "accounts/signup_doctor.html")


@login_required
def dashboard(request):
    """Sends each user to the right space for their role."""
    role = request.user.role
    if request.user.is_superuser or request.user.is_staff or role == User.Role.ADMIN:
        return redirect("admin:index")
    if role == User.Role.DOCTOR:
        return redirect("doctor_dashboard")
    if role == User.Role.PATIENT:
        return redirect("patient_dashboard")
    return render(request, "accounts/other_role.html")


@login_required
def patient_dashboard(request):
    profile = getattr(request.user, "patient_profile", None)
    if request.user.role != User.Role.PATIENT or profile is None:
        raise PermissionDenied
    booked = Appointment.objects.filter(patient=profile, status=Appointment.Status.BOOKED)
    appointments = (
        booked.filter(start__gte=timezone.now())
        .select_related("doctor__user", "doctor__specialty")
        .order_by("start")
    )
    cancelled = (
        Appointment.objects.filter(patient=profile, status=Appointment.Status.CANCELLED)
        .select_related("doctor__user", "doctor__specialty", "cancelled_by")
        .order_by("-cancelled_at")[:5]
    )
    return render(request, "accounts/patient_dashboard.html", {
        "patient": profile, "appointments": appointments, "cancelled": cancelled,
    })


@login_required
def doctor_dashboard(request):
    doctor = getattr(request.user, "doctor_profile", None)
    if request.user.role != User.Role.DOCTOR or doctor is None:
        raise PermissionDenied
    appointments = []
    if doctor.is_verified:  # an unverified doctor sees no patient data
        appointments = (
            Appointment.objects.filter(
                doctor=doctor, start__gte=timezone.now(), status=Appointment.Status.BOOKED
            )
            .select_related("patient")
            .order_by("start")
        )
    return render(request, "accounts/doctor_dashboard.html", {"doctor": doctor, "appointments": appointments})
