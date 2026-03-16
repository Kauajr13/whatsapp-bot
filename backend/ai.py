import os
import logging
import google.generativeai as genai
from database import get_config, get_history

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model


def classify_intent(message: str) -> str:
    intents = {
        "greeting": ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hello", "hi"],
        "price": ["preço", "preco", "valor", "quanto", "custo", "custa"],
        "hours": ["horário", "horario", "hora", "funcionamento", "aberto", "fecha"],
        "address": ["endereço", "endereco", "onde", "localização", "localizacao", "fica"],
        "human": ["atendente", "humano", "pessoa", "falar com alguém", "falar com alguem"],
        "thanks": ["obrigado", "obrigada", "valeu", "grato", "grata", "thanks"],
        "bye": ["tchau", "bye", "até logo", "ate logo", "adeus"],
    }
    lower = message.lower()
    for intent, keywords in intents.items():
        if any(kw in lower for kw in keywords):
            return intent
    return "unknown"


def generate_response(phone: str, message: str, context: dict) -> str:
    config = get_config()
    if config.get("ai_enabled") != "true":
        return None

    history = get_history(phone, limit=10)
    conversation = []
    for msg in history[-6:]:
        role = "user" if msg["direction"] == "in" else "model"
        conversation.append({"role": role, "parts": [msg["content"]]})

    system = f"""Você é {config.get('bot_name', 'Assistente')}, um atendente virtual.
Responda de forma direta, educada e concisa.
Não se identifique como IA a menos que perguntado diretamente.
Se não souber responder, diga que vai verificar e retornar em breve.
Contexto do negócio: {context.get('business_context', 'empresa geral')}.
Horário de atendimento: {config.get('business_hours_start')} às {config.get('business_hours_end')}.
Responda sempre em português do Brasil."""

    try:
        model = _get_model()
        full_history = conversation + [{"role": "user", "parts": [message]}]

        if len(full_history) == 1:
            response = model.generate_content(
                f"{system}\n\nMensagem do cliente: {message}"
            )
        else:
            chat = model.start_chat(history=conversation)
            response = chat.send_message(message)

        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return None
