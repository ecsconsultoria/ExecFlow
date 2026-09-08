"""
Utilitário de tradução automática para geração de PDFs.
Usa deep-translator (Google Translate, sem API key).
Se a tradução falhar por qualquer motivo, retorna o texto original.
"""

import logging
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
# PDF reutilizam a tradução sem chamar o Google de novo (evita o padrão
# "1ª geração OK, 2ª geração falha" por limite de chamadas do serviço).
_CACHE: dict[tuple[str, str], str] = {}
_CACHE_MAX = 512


def translate_obs(text: str, target_lang: str) -> str:
    """Traduz `text` para `target_lang` ('en', 'pt', etc.).
    Se target_lang == 'pt' ou texto estiver vazio, devolve original.
    Falhas são silenciosas — retorna o texto original."""
    if not text or not text.strip():
        return text
    if target_lang == "pt":
        return text
    key = (text.strip(), target_lang)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="auto", target=target_lang).translate(text)
        # Descarta "traduções" que são páginas de erro do serviço: o Google
        # pode responder 200 com corpo de erro em chamadas repetidas e o
        # deep-translator entrega o texto da página como se fosse a tradução.
        if translated and not _ERROR_MARKERS.search(translated):
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()
            _CACHE[key] = translated
            return translated
        _log.warning("Tradução descartada (página de erro do serviço) — usando texto original")
        return text
    except Exception as exc:
        _log.warning("Tradução falhou (%s) — usando texto original: %s", exc, text[:60])
        return text
