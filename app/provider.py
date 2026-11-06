"""Server-side Gemini REST adapter; only lab values and units leave the app."""
import json
import math
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app

INSTRUCTIONS = (
    "Review only the supplied blood-test values and assumed units. Return 1-3 "
    "concise plain-text sentences about a possible risk or abnormal pattern. "
    "Use cautious language such as 'may' or 'could'; do not give a definitive "
    "diagnosis or treatment advice. Do not invent age, sex, symptoms, fasting "
    "status, medical history, or other clinical context. State that these values "
    "alone cannot establish a diagnosis. If context is insufficient, say so."
)
UNITS = {"glucose": "mg/dL", "haemoglobin": "g/dL", "cholesterol": "mg/dL"}


class PredictionError(Exception):
    """Safe user-facing error with no provider bodies or credentials."""


def validate_remarks(remarks):
    if not isinstance(remarks, str) or not remarks.strip() or len(remarks) > 5000:
        raise PredictionError("Gemini returned an empty or malformed review. Please retry.")
    return remarks.strip()


def parse_response(payload):
    try:
        if not isinstance(payload, dict) or payload.get("error"):
            raise ValueError
        feedback = payload.get("promptFeedback", {})
        if not isinstance(feedback, dict) or feedback.get("blockReason"):
            raise ValueError
        candidates = payload["candidates"]
        if not isinstance(candidates, list) or len(candidates) != 1:
            raise ValueError
        candidate = candidates[0]
        if candidate["finishReason"] != "STOP":
            raise ValueError
        parts = candidate["content"]["parts"]
        if not isinstance(parts, list) or not parts:
            raise ValueError
        text = []
        for part in parts:
            if not isinstance(part, dict):
                raise ValueError
            if part.get("thought") is True:
                continue
            if not isinstance(part.get("text"), str):
                raise ValueError
            text.append(part["text"])
        return validate_remarks("".join(text))
    except (KeyError, TypeError, ValueError, IndexError):
        raise PredictionError("Gemini returned an empty, blocked, or malformed review. Please retry.") from None


class GeminiProvider:
    def __init__(self, api_key, model="gemini-flash-latest", timeout=30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @classmethod
    def from_environment(cls):
        return cls(os.getenv("GEMINI_API_KEY", "").strip(),
                   os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip(),
                   os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))

    def __call__(self, clinical):
        if not self.api_key:
            raise PredictionError("Gemini is not configured. Set GEMINI_API_KEY locally, restart the app, and retry.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.model):
            raise PredictionError("Gemini model configuration is invalid. Check GEMINI_MODEL and retry.")
        try:
            timeout = float(self.timeout)
            if not math.isfinite(timeout) or not 0 < timeout <= 120:
                raise ValueError
        except (TypeError, ValueError):
            raise PredictionError("Set GEMINI_TIMEOUT_SECONDS above 0 and at most 120, then restart.") from None
        labs = {key: clinical[key] for key in UNITS}
        labs["units"] = dict(UNITS)
        body = {
            "systemInstruction": {"parts": [{"text": INSTRUCTIONS}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(labs, allow_nan=False)}]}],
            "generationConfig": {"responseMimeType": "text/plain", "maxOutputTokens": 2048},
        }
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise ValueError
                payload = json.loads(raw)
        except HTTPError as error:
            if error.code in (401, 403):
                message = "Gemini authentication failed. Check the local API key and permissions, then retry."
            elif error.code == 429:
                message = "Gemini quota or rate limit reached. Check quota or wait, then retry."
            elif error.code == 404:
                message = "Gemini model was not found. Check GEMINI_MODEL, restart, and retry."
            else:
                message = "Gemini could not complete the request. Please retry."
            raise PredictionError(message) from None
        except (TimeoutError, URLError, OSError):
            raise PredictionError("Gemini timed out or could not be reached. Please retry.") from None
        except (ValueError, UnicodeError):
            raise PredictionError("Gemini returned malformed data. Please retry.") from None
        return parse_response(payload)


def review_patient(data):
    provider = current_app.config.get("REVIEW_PROVIDER")
    if provider is None:
        raise PredictionError("Gemini is not configured. Configure the provider and retry.")
    clinical = {key: data[key] for key in UNITS}
    clinical["units"] = dict(UNITS)
    try:
        return validate_remarks(provider(clinical)), "complete"
    except PredictionError:
        raise
    except Exception:
        raise PredictionError("AI review failed. Please retry; no changes were saved.") from None
