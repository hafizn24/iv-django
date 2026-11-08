import base64
import os

import httpx
from django.conf import settings

from .models import AuditLog


def log_action(user, action, entity, entity_id=None, detail=None):
    AuditLog.objects.create(
        user=user, action=action, entity=entity, entity_id=entity_id, detail=detail or {}
    )


def upload_nric_image(file, visitor_ref: str) -> str:
    """Upload to Supabase Storage, return the object path."""
    base = settings.SUPABASE_URL.rstrip("/")
    bucket = settings.SUPABASE_BUCKET
    ext = os.path.splitext(file.name)[1].lower() or ".jpg"
    path = f"nric/{visitor_ref}{ext}"
    resp = httpx.post(
        f"{base}/storage/v1/object/{bucket}/{path}",
        headers={
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Content-Type": file.content_type or "application/octet-stream",
        },
        content=file.read(),
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Storage upload failed: {resp.status_code} {resp.text}")
    return path


def ocr_nric(image_bytes: bytes, content_type: str) -> dict:
    """Call an OpenAI-compatible vision API to extract name + NRIC number."""
    data_uri = f"data:{content_type or 'image/jpeg'};base64,{base64.b64encode(image_bytes).decode()}"
    resp = httpx.post(
        f"{settings.OCR_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.OCR_API_KEY}"},
        json={
            "model": settings.OCR_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "This is a photo of a Malaysian NRIC (MyKad). Extract the holder's full name and the 12-digit NRIC number (with dashes removed). Reply ONLY with JSON like {\"full_name\": \"...\", \"nric_number\": \"...\"} using empty strings if unreadable.",
                        },
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            "max_tokens": 200,
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()
    # strip possible markdown fences
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    import json

    return json.loads(text)
