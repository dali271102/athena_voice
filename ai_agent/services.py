# The booking logic now lives in the appointments app, so Athena and the
# manual booking pages share exactly the same rules.
from appointments.services import book_appointment, get_available_doctors, list_specialties  # noqa: F401
