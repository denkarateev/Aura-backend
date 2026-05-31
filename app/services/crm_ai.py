"""
CRM AI insights — an LLM ("нейронка") that reads the lounge's guest base and the
deterministic scoring, then writes a short situational analysis and a prioritised
list of concrete retention actions ("кого вернуть и что им дать").

Provider-agnostic: any OpenAI-compatible Chat Completions endpoint
(OpenAI / OpenRouter / a Kie.ai OpenAI-compatible gateway). Configured via
LLM_API_BASE / LLM_API_KEY / LLM_MODEL. If no key is set, ai_enabled() is False
and the endpoint returns 503 — so deploying without a key is safe.
"""

import json
import urllib.request
import urllib.error

from app.core.config import LLM_API_BASE, LLM_API_KEY, LLM_MODEL


def ai_enabled() -> bool:
    return bool(LLM_API_KEY)


class AIError(Exception):
    pass


def _chat(messages, *, max_tokens: int = 900, temperature: float = 0.4, timeout: int = 45) -> str:
    """One OpenAI-compatible chat-completions call. Returns the message content."""
    if not LLM_API_KEY:
        raise AIError("LLM is not configured")
    url = LLM_API_BASE.rstrip("/") + "/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise AIError(f"LLM HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise AIError(f"LLM request failed: {exc}") from exc

    try:
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise AIError(f"Unexpected LLM response shape: {exc}") from exc


def _extract_json(text: str) -> dict:
    """Pull the first {...} JSON object out of an LLM reply (handles code fences
    and prose around it). Returns {} if nothing parseable is found."""
    if not text:
        return {}
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(t[start:end + 1])
    except Exception:
        return {}


def analyze_guest_base(*, lounge_title: str, summary: dict, segments: list,
                       sample_guests: list, commission_percent: float) -> dict:
    """Ask the LLM to analyse the guest base. Returns
    {analysis: str, actions: [str], model: str}. Raises AIError on failure."""
    data = {
        "lounge": lounge_title,
        "сводка": summary,
        "сегменты": segments,
        "гости_под_возврат": sample_guests,
        "комиссия_платформы_процент": commission_percent,
    }
    system = (
        "Ты — аналитик удержания гостей для сети кальянных лаунжей в России. "
        "Анализируешь данные RFM-сегментации (Recency/Frequency/Monetary) и пишешь "
        "кратко, конкретно, на русском, с цифрами и рублёвыми офферами. "
        "Не выдумывай данные, опирайся только на переданные числа."
    )
    user = (
        "Вот данные по гостевой базе заведения (JSON):\n"
        + json.dumps(data, ensure_ascii=False, indent=2)
        + "\n\nСделай разбор и план удержания. Ответь СТРОГО одним JSON-объектом вида:\n"
        '{"analysis": "<2-4 предложения: что происходит с базой, главные риски и возможности>", '
        '"actions": ["<5-7 конкретных действий: кому что дать, какой оффер/бонус в ₽, по какому каналу, '
        'с какой срочностью — чтобы гости возвращались>"]}\n'
        "Только JSON, без пояснений вокруг."
    )
    content = _chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    parsed = _extract_json(content)
    analysis = (parsed.get("analysis") or "").strip()
    actions = parsed.get("actions") or []
    if not isinstance(actions, list):
        actions = [str(actions)]
    actions = [str(a).strip() for a in actions if str(a).strip()][:8]

    # Fallback: if the model didn't return clean JSON, surface its raw prose so
    # the feature still gives value rather than erroring.
    if not analysis and not actions:
        analysis = content.strip()[:1200]

    return {"analysis": analysis, "actions": actions, "model": LLM_MODEL}
