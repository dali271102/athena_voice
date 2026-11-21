from django.contrib import admin
from .models import Specialty, Doctor, WorkingHours, Patient, Appointment

for m in (Specialty, Doctor, WorkingHours, Patient, Appointment):
    admin.site.register(m)