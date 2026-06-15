"""
Utilitário de tradução automática para geração de PDFs.
Usa deep-translator (Google Translate, sem API key).
Se a tradução falhar por qualquer motivo, retorna o texto original.
"""

import logging

_log = logging.getLogger(__name__)


def translate_obs(text: str, target_lang: str) -> str:
    """Traduz `text` para `target_lang` ('en', 'pt', etc.).
    Se target_lang == 'pt' ou texto estiver vazio, devolve original.
    Falhas são silenciosas — retorna o texto original."""
    if not text or not text.strip():
        return text
    if target_lang == "pt":
        return text
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="auto", target=target_lang).translate(text)
        return translated or text
    except Exception as exc:
        _log.warning("Tradução falhou (%s) — usando texto original: %s", exc, text[:60])
        return text
