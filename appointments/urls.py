from django.urls import path

from . import views

urlpatterns = [
    path("patient/book/", views.book_specialty, name="book_specialty"),
    path("patient/book/confirm/", views.book_confirm, name="book_confirm"),
    path("patient/book/<int:specialty_id>/", views.book_slots, name="book_slots"),
    path("appointments/<int:pk>/cancel/", views.cancel_appointment, name="cancel_appointment"),
    path("doctor/hours/", views.doctor_hours, name="doctor_hours"),
    path("doctor/hours/<int:pk>/delete/", views.doctor_hours_delete, name="doctor_hours_delete"),
]
