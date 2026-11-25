import json
import os
from datetime import date

from django.utils import timezone
from openai import OpenAI

from . import services

TOOLS = [
    {"type": "function", "function": {
        "name": "list_specialties",
        "description": "List the medical specialties available at the hospital.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_available_doctors",
        "description": "Get doctors of a specialty with their free time slots on a given date. "
                       "An empty list means nothing is free that day: try another date.",
        "parameters": {"type": "object", "properties": {
            "specialty": {"type": "string", "description": "Exact name from list_specialties"},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
        }, "required": ["specialty", "date"]},
    }},
    {"type": "function", "function": {
        "name": "book_appointment",
        "description": "Book an appointment. Only call after the patient confirmed the doctor, date and time.",
        "parameters": {"type": "object", "properties": {
            "doctor_id": {"type": "integer"},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "time": {"type": "string", "description": "HH:MM"},
            "patient_name": {"type": "string", "description": "Full name exactly as the patient said it. Never guess."},
            "phone": {"type": "string"},
            "symptoms": {"type": "string", "description": "Short summary of the symptoms"},
        }, "required": ["doctor_id", "date", "time", "patient_name"]},
    }},
]

LANG_RULES = {
    "fr": "The patient speaks French. Reply in French.",
    "en": "The patient speaks English. Reply in English.",
    "ar": ("The patient speaks Arabic. Reply in simple Tunisian Arabic (derja tounsia) written in Arabic script, "
           "the way a friendly Tunisian nurse talks to a patient: short sentences and everyday words. "
           "You may keep French words Tunisians commonly use, such as rendez-vous and docteur."),
}


def system_prompt(lang="fr", patient=None):
    today = timezone.localdate()
    prompt = f"""You are Athena, the voice assistant of a Tunisian hospital. Today is {today} ({today.strftime('%A')}).
Your job: listen to the patient's symptoms, orient them to the right specialty, and book an appointment.

Rules:
- {LANG_RULES.get(lang, LANG_RULES['fr'])}
- Keep answers SHORT. Plain spoken sentences only: no markdown, no asterisks, no bullet lists, no emojis. Your words are read aloud.
- You do NOT diagnose and you do NOT give treatments. You only orient to a specialty.
- Ask 2 or 3 short follow-up questions about the symptoms (duration, severity) before choosing.
- EMERGENCY: if the patient mentions chest pain with difficulty breathing, signs of stroke, severe bleeding,
  loss of consciousness or suicidal thoughts, stop everything and tell them to call 190 (SAMU) or go to the
  emergency room immediately. Do not book an appointment.
- Choose the specialty ONLY from list_specialties. If unsure, use general medicine.
- Never invent doctors or time slots: use get_available_doctors. If nothing is free, try the next days.
- Booking steps, in this order: (1) propose a doctor and a slot, (2) the patient agrees to the slot,
  (3) ask for the patient's full name and phone number, (4) only when you have heard the name from the patient,
  call book_appointment, (5) confirm out loud the doctor, the date, the time and the name.
  NEVER invent, guess or reuse a name. If the patient has not told you their name, ask for it, even if they already said yes to the slot.
- If a tool returns an error or ok=false, explain simply and offer another slot."""
    if patient is not None:
        prompt += (
            f"\n- IDENTIFIED PATIENT: this patient is logged in as {patient.full_name} "
            f"(phone: {patient.phone or 'unknown'}). Do NOT ask for their name. Use exactly this name for "
            "patient_name when booking. If the phone is unknown, ask for it before booking. "
            "This overrides the rule about asking for the name."
        )
    return prompt


def _run_tool(name, args, patient=None):
    try:
        if name == "list_specialties":
            return services.list_specialties()
        if name == "get_available_doctors":
            return services.get_available_doctors(args["specialty"], date.fromisoformat(args["date"]))
        if name == "book_appointment":
            return services.book_appointment(
                int(args["doctor_id"]), date.fromisoformat(args["date"]), args["time"],
                args.get("patient_name", ""), args.get("phone", ""), args.get("symptoms", ""),
                patient=patient,
            )
    except Exception as e:
        return {"error": str(e)}
    return {"error": f"unknown tool {name}"}


def chat(history, user_text, lang="fr", patient=None, max_steps=6):
    """One patient turn. `history` = previous messages (no system prompt).
    `lang` = "fr", "ar" or "en". `patient` = the logged-in Patient, if any.
    Returns (reply_text, new_history)."""
    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ.get("LLM_BASE_URL"),
    )
    model = os.environ["LLM_MODEL"]

    messages = [{"role": "system", "content": system_prompt(lang, patient)}] + history
    messages.append({"role": "user", "content": user_text})

    for _ in range(max_steps):
        resp = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        msg = resp.choices[0].message

        if not msg.tool_calls:
            reply = msg.content or ""
            messages.append({"role": "assistant", "content": reply})
            return reply, messages[1:]

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [{
                "id": c.id, "type": "function",
                "function": {"name": c.function.name, "arguments": c.function.arguments},
            } for c in msg.tool_calls],
        })
        for c in msg.tool_calls:
            args = json.loads(c.function.arguments or "{}")
            result = _run_tool(c.function.name, args, patient)
            messages.append({
                "role": "tool", "tool_call_id": c.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    return "Désolé, je n'ai pas pu terminer. Pouvez-vous répéter ?", messages[1:]
