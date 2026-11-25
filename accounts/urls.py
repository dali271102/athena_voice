from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/patient/", views.patient_signup, name="patient_signup"),
    path("signup/doctor/", views.doctor_signup, name="doctor_signup"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("patient/", views.patient_dashboard, name="patient_dashboard"),
    path("doctor/", views.doctor_dashboard, name="doctor_dashboard"),
]
