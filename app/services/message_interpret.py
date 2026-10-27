"""message_interpret.py — interpretação de mensagens (WhatsApp/e-mail) via API DeepSeek.

Extrai os campos do RFQ a partir do texto colado pelo operador.
Fase de teste: rota pública sem token (token será implantado após validação).

Não persiste nada — apenas devolve o JSON estruturado.
"""
from __future__ import annotations

import json
import os
import urllib.request

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """Você é um assistente de uma empresa de transporte executivo (Executive Car SP).
Sua tarefa: extrair de mensagens recebidas (WhatsApp/e-mail) os dados para preencher
um orçamento (RFQ) no sistema ExecFlow.

Responda SEMPRE com um único JSON, sem texto fora do JSON, com este formato:

{
  "tipo_mensagem": "orcamento_direto" | "consulta_simples" | "pedido_tarifario" | "parceiro",
  "cliente_nome": "..." | null,
  "contato_nome": "..." | null,
  "email": "..." | null,
  "telefone": "..." | null,
  "idioma": "pt" | "en",
  "itens": [
    {
      "descricao": "texto do serviço (ex.: Transfer GRU Airport, Diária 10h + 100km Franquia)" | null,
      "categoria_veiculo": "nome da categoria ExecFlow (Sedan Executivo, Sedan Premium, SUV Executivo, Minivan Executivo, Van Executiva, Microônibus Executivo, Ônibus Executivo, variantes Blindado/Premium)" | null,
      "motorista": "Bilíngue" | "Monolíngue" | null,
      "data": "AAAA-MM-DD" | null,
      "hora": "HH:MM" | null,
      "origem": "..." | null,  // opcional
      "destino": "..." | null,  // opcional
      "passageiros": 0 | null,  // opcional
      "quantidade": 0 | null
    }
  ],
  "observacoes": "informações que não cabem nos campos acima (bagagens, perguntas comerciais, condições)" | null,
  "incompletude": ["apenas o que impede o orçamento (ex.: data/hora de serviço específico, categoria ambígua, contato do cliente). NUNCA liste origem, destino ou passageiros aqui."]
}

REGRAS OBRIGATÓRIAS:
1. NUNCA invente dados. Se a mensagem não informa, use null.
2. NUNCA invente preços. Preço não é campo de extração.
3. Datas relativas (ex.: "amanhã") vão em "incompletude" com a explicação — não chute a data.
4. Veículos citados em linguagem natural devem ser mapeados para a categoria ExecFlow mais próxima; se ambíguo, null e registre em "incompletude".
5. "English-Speaking" ou "inglês" no motorista -> "Bilíngue"; "Portuguese" -> "Monolíngue".
6. Mensagens que pedem tarifário/frota (sem um serviço único) são "pedido_tarifario": extraia os serviços citados como itens com quantidade null e jogue as perguntas comerciais em "observacoes".
7. Preencha "observacoes" com detalhes operacionais importantes (bagagens, pontos de atenção).
8. A lista "incompletude" não deve ter itens duplicados.
9. origem, destino e passageiros são OPCIONAIS: se a mensagem não informar, use null e NÃO os liste em "incompletude" (incompletude é só para o que impede o orçamento: data/hora de serviço específico, categoria ambígua, contato do cliente)."""


def interpret_message(text: str) -> dict:
    """Interpreta a mensagem e devolve o JSON estruturado dos campos do RFQ."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY não configurada no servidor.")
    text = (text or "").strip()
    if not text:
        raise ValueError("Mensagem vazia.")
    if len(text) > 8000:
        raise ValueError("Mensagem muito longa (máx. 8000 caracteres).")

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 4000,
        "temperature": 0,
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    resultado = json.loads(content)
    # Garantia determinística: origem, destino e passageiros são opcionais —
    # removemos da incompletude qualquer menção a eles, mesmo que o modelo insista.
    if isinstance(resultado, dict) and isinstance(resultado.get("incompletude"), list):
        resultado["incompletude"] = [
            item
            for item in resultado["incompletude"]
            if not any(p in str(item).lower() for p in ("passageiro", "origem", "destino", "pax"))
        ]
    return resultado
