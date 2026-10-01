"""Shared Gemini access (google-genai SDK) with automatic model fallback.

Models are tried in order; if one is overloaded (503), rate limited (429) or
retired (404), the next is used. Override with GEMINI_MODEL /
GEMINI_FALLBACK_MODEL in Backend/.env. The "-latest" aliases track Google's
current models, so they don't break when a specific version is retired.
"""
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger("gemini_client")

RETRYABLE_CODES = {404, 429, 500, 503}


class GeminiUnavailable(Exception):
    """No configured Gemini model could answer."""


_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiUnavailable("GEMINI_API_KEY is not set in Backend/.env")
        _client = genai.Client(api_key=api_key)
    return _client


def model_chain():
    return [
        # Lite first: fast (1-4s) and accurate enough for receipts and short text,
        # while the full Flash model is often overloaded and slow to fail.
        os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest"),
        os.getenv("GEMINI_FALLBACK_MODEL", "gemini-flash-latest"),
    ]


def generate_json(contents, temperature: float = 0) -> dict:
    """Send `contents` (a prompt string, or a list of Parts and strings) and return parsed JSON.

    temperature 0 for extraction (parsing, receipts); a little higher for conversational text.
    """
    client = _get_client()
    config = types.GenerateContentConfig(temperature=temperature, response_mime_type="application/json")
    last_error = None

    for model in model_chain():
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            return json.loads(response.text)
        except errors.APIError as e:
            last_error = e
            if e.code in RETRYABLE_CODES:
                logger.warning("Gemini model %s unavailable (%s), trying next", model, e.code)
                continue
            raise GeminiUnavailable(f"Gemini request failed: {e.message}") from e
        except (json.JSONDecodeError, TypeError) as e:
            last_error = e
            logger.warning("Gemini model %s returned non-JSON output, trying next", model)

    raise GeminiUnavailable(f"All Gemini models failed: {last_error}")
