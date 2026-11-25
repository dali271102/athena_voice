from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.db import transaction

from appointments.models import Doctor, Specialty
from patients.models import Patient

User = get_user_model()


class BaseSignUpForm(UserCreationForm):
    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Email", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")


class PatientSignUpForm(BaseSignUpForm):
    phone = forms.CharField(label="Téléphone", max_length=20)

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PATIENT  # the role is set here, never chosen by the visitor
        user.save()
        Patient.objects.create(
            user=user, full_name=user.get_full_name(), phone=self.cleaned_data["phone"]
        )
        return user


class DoctorSignUpForm(BaseSignUpForm):
    specialty = forms.ModelChoiceField(
        queryset=Specialty.objects.all(), label="Spécialité", empty_label="Choisir…"
    )
    license_number = forms.CharField(
        label="Numéro d'inscription à l'Ordre des médecins", max_length=50
    )

    def clean_license_number(self):
        number = self.cleaned_data["license_number"].strip()
        if Doctor.objects.filter(license_number__iexact=number).exists():
            raise ValidationError("Ce numéro d'inscription est déjà utilisé.")
        return number

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.DOCTOR  # a doctor account starts UNVERIFIED (see Doctor.is_verified)
        user.save()
        Doctor.objects.create(
            user=user,
            specialty=self.cleaned_data["specialty"],
            license_number=self.cleaned_data["license_number"],
        )
        return user
