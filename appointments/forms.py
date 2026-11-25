from django import forms

from .models import WorkingHours


class WorkingHoursForm(forms.ModelForm):
    class Meta:
        model = WorkingHours
        fields = ["weekday", "start", "end", "slot_minutes"]
        widgets = {
            "start": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, doctor, **kwargs):
        super().__init__(*args, **kwargs)
        # the doctor is always the logged-in one (never taken from the form), so the overlap check works
        self.instance.doctor = doctor
