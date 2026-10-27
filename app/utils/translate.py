"""
Utilitário de tradução automática para geração de PDFs e páginas públicas.
Tradutor principal: API DeepSeek (DEEPSEEK_API_KEY) — confiável, sem limite
de requisições por segundo. Reserva: deep-translator (Google Translate).
Se tudo falhar, retorna o texto original.
"""

import logging
import os
import re

_log = logging.getLogger(__name__)

# Assinaturas de páginas de erro do Google/proxy: se a "tradução" contém uma
# delas, o serviço respondeu com página de erro e devolvemos o texto original.
_ERROR_MARKERS = re.compile(
    r"That's an error|That's all we know|Server Error|Bad Gateway|"
    r"Error\s+[45]\d{2}|please try again later|"
    r"<html|<title>Error",
    re.IGNORECASE,
)

# Cache em memória de traduções bem-sucedidas: gerações consecutivas do mesmo
# PDF/página reutilizam a tradução sem chamar o serviço de novo (evita o padrão
# "1ª geração OK, 2ª geração falha" por limite de chamadas do serviço).
_CACHE: dict[tuple[str, str], str] = {}
_CACHE_MAX = 512


def _translate_deepseek(text: str, target_lang: str) -> str | None:
    """Tradução via API DeepSeek. Devolve None em qualquer falha."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return None
    try:
        import requests
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system",
                 "content": ("Você é um tradutor. Traduza o texto para o idioma pedido e "
                             "responda SOMENTE com a tradução, sem aspas nem comentários.")},
                {"role": "user", "content": f"Traduza para '{target_lang}':\n{text}"},
            ],
            "temperature": 0,
            "max_tokens": 2000,
        }
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        out = (r.json()["choices"][0]["message"]["content"] or "").strip()
        if out and not _ERROR_MARKERS.search(out):
            return out
    except Exception as exc:
        _log.warning("Tradução DeepSeek falhou (%s)", exc)
    return None


def _translate_google(text: str, target_lang: str) -> str | None:
    """Tradução via deep-translator (Google). Devolve None em qualquer falha."""
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="auto", target=target_lang).translate(text)
        if translated and not _ERROR_MARKERS.search(translated):
            return translated
        _log.warning("Tradução descartada (página de erro do serviço)")
    except Exception as exc:
        _log.warning("Tradução Google falhou (%s)", exc)
    return None


def translate_obs(text: str, target_lang: str) -> str:
    """Traduz `text` para `target_lang` ('en', 'pt', etc.).
    Se target_lang == 'pt' ou texto estiver vazio, devolve original.
    Ordem: DeepSeek → Google → texto original (falhas são silenciosas)."""
    if not text or not text.strip():
        return text
    if target_lang == "pt":
        return text
    key = (text.strip(), target_lang)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    translated = _translate_deepseek(text, target_lang)
    if translated is None:
        translated = _translate_google(text, target_lang)
    if translated is None:
        _log.warning("Nenhum tradutor disponível — usando texto original")
        return text
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = translated
    return translated
