import os
import logging
import google.generativeai as genai
from database import get_config, get_history

logger = logging.getLogger(__name__)

_model = None


def _get_model(system_prompt: str):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-3.1-flash-lite-preview",
        system_instruction=system_prompt,
    )


def classify_intent(message: str) -> str:
    intents = {
        "greeting": ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hello", "hi"],
        "thanks": ["obrigado", "obrigada", "valeu", "grato", "grata", "thanks"],
        "bye": ["tchau", "bye", "até logo", "ate logo", "adeus"],
    }
    lower = message.lower()
    for intent, keywords in intents.items():
        if any(kw in lower for kw in keywords):
            return intent
    return "unknown"


def build_system_prompt(config: dict, context: dict) -> str:
    return f"""Você é {config.get('bot_name', 'Assistente')}, atendente da loja X.

Tom de voz: descontraído mas profissional. Use linguagem simples, sem termos técnicos.
Tamanho das respostas: máximo 3 frases. Seja direto.
Não use emojis em excesso.
Não se identifique como IA a menos que perguntado diretamente.
Se não souber responder, diga: "Vou verificar isso e te retorno em breve!"

Sobre o negócio:
- Vendemos roupas femininas tamanhos P ao GG
- Aceitamos PIX, cartão de crédito e boleto
- Entregamos para todo o Brasil, frete grátis acima de R$150
- Trocas em até 7 dias após recebimento

Horário de atendimento: {config.get('business_hours_start')} às {config.get('business_hours_end')}.
Responda sempre em português do Brasil."""


def generate_response(phone: str, message: str, context: dict) -> str:
    config = get_config()
    if config.get("ai_enabled") != "true":
        return None

    system_prompt = build_system_prompt(config, context)

    history = get_history(phone, limit=10)
    conversation = []
    for msg in history[-6:]:
        role = "user" if msg["direction"] == "in" else "model"
        conversation.append({"role": role, "parts": [msg["content"]]})

    try:
        # recria o model sempre com o system_instruction atualizado
        model = _get_model(system_prompt)

        if not conversation:
            response = model.generate_content(message)
        else:
            chat = model.start_chat(history=conversation)
            response = chat.send_message(message)

        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return None
