import asyncio
import json
import logging
import os

import edge_tts
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from openai import OpenAI

from .agent import chat

log = logging.getLogger(__name__)


def home(request):
    return render(request, "core/home.html")


@require_POST
def api_chat(request):
    try:
        data = json.loads(request.body)
        text = data.get("message", "").strip()
        lang = data.get("lang", "fr")
    except (ValueError, AttributeError):
        return JsonResponse({"error": "bad request"}, status=400)
    if not text:
        return JsonResponse({"error": "empty message"}, status=400)

    history = request.session.get("history", [])
    try:
        reply, history = chat(history, text, lang)
    except Exception:
        log.exception("Athena chat failed")
        return JsonResponse({"reply": "Désolé, un problème technique est survenu. Pouvez-vous répéter ?"})

    request.session["history"] = history
    return JsonResponse({"reply": reply})


@require_POST
def api_reset(request):
    request.session.pop("history", None)
    return JsonResponse({"ok": True})


@require_POST
def api_transcribe(request):
    audio = request.FILES.get("audio")
    lang = request.POST.get("lang", "fr")
    if not audio or audio.size == 0:
        return JsonResponse({"text": ""})
    if audio.size > 10 * 1024 * 1024:
        return JsonResponse({"text": "", "error": "too_big"}, status=413)

    mime = (audio.content_type or "audio/webm").split(";")[0]
    ext = "mp4" if "mp4" in mime else "webm"
    try:
        client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ.get("LLM_BASE_URL"))
        result = client.audio.transcriptions.create(
            model=(os.environ.get("STT_MODEL_AR", "whisper-large-v3") if lang == "ar"
                   else os.environ.get("STT_MODEL", "whisper-large-v3-turbo")),
            file=(f"speech.{ext}", audio.read(), mime),
            language=lang,
        )
        return JsonResponse({"text": result.text})
    except Exception:
        log.exception("Transcription failed")
        return JsonResponse({"text": "", "error": "stt_failed"})


VOICES = {
    "fr": "fr-FR-DeniseNeural",
    "en": "en-US-JennyNeural",
    "ar": "ar-TN-ReemNeural",  # male alternative: ar-TN-HediNeural
}


async def _synth(text, voice):
    data = b""
    async for chunk in edge_tts.Communicate(text, voice).stream():
        if chunk["type"] == "audio":
            data += chunk["data"]
    return data


@require_POST
def api_tts(request):
    try:
        body = json.loads(request.body)
        text = body.get("text", "").strip()[:1000]
        if not text:
            return HttpResponse(status=400)
        voice = VOICES.get(body.get("lang", "fr"), VOICES["fr"])
        audio = asyncio.run(_synth(text, voice))
    except Exception:
        log.exception("TTS failed")
        return HttpResponse(status=502)
    return HttpResponse(audio, content_type="audio/mpeg")