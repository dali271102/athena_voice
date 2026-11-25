from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("athena/", views.athena, name="athena"),
    path("api/chat/", views.api_chat, name="api_chat"),
    path("api/reset/", views.api_reset, name="api_reset"),
    path("api/transcribe/", views.api_transcribe, name="api_transcribe"),
    path("api/tts/", views.api_tts, name="api_tts"),
]
