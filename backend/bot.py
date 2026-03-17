import re
import logging
from datetime import datetime, time
from database import get_rules, get_config, log_message
from ai import classify_intent, generate_response

logger = logging.getLogger(__name__)


def is_business_hours(config: dict) -> bool:
    now = datetime.now()
    business_days = [int(d) for d in config.get("business_days", "0,1,2,3,4").split(",")]
    if now.weekday() not in business_days:
        return False
    try:
        start_h, start_m = map(int, config["business_hours_start"].split(":"))
        end_h, end_m = map(int, config["business_hours_end"].split(":"))
        start = time(start_h, start_m)
        end = time(end_h, end_m)
        return start <= now.time() <= end
    except (KeyError, ValueError):
        return True


def match_rule(message: str, rule: dict) -> bool:
    trigger = rule["trigger"].lower()
    msg = message.lower()
    match_type = rule.get("match_type", "contains")
    if match_type == "exact":
        return msg == trigger
    elif match_type == "startswith":
        return msg.startswith(trigger)
    elif match_type == "regex":
        return bool(re.search(trigger, msg, re.IGNORECASE))
    else:
        return trigger in msg


def process_message(phone: str, message: str, context: dict = None) -> str:
    context = context or {}
    config = get_config()

    log_message(phone, "in", message)
    logger.info(f"Processing: '{message[:60]}' from {phone}")

    if not is_business_hours(config):
        response = config.get("off_hours_message", "Fora do horário de atendimento.")
        logger.info(f"Outside business hours -> off_hours_message")
        log_message(phone, "out", response, intent="off_hours")
        return response

    intent = classify_intent(message)
    logger.info(f"Intent: {intent}")

    if intent == "greeting":
        response = config.get("greeting_message", "Olá! Como posso ajudar?")
        log_message(phone, "out", response, intent=intent)
        return response

    if intent == "bye":
        response = "Até logo! Qualquer dúvida, é só chamar."
        log_message(phone, "out", response, intent=intent)
        return response

    rules = get_rules(active_only=True)
    logger.info(f"Checking {len(rules)} rule(s)")
    for rule in rules:
        if match_rule(message, rule):
            logger.info(f"Rule matched: id={rule['id']} trigger='{rule['trigger']}'")
            response = rule["response"]
            log_message(phone, "out", response, intent=f"rule:{rule['id']}")
            return response

    ai_fallback = config.get("ai_fallback")
    ai_enabled = config.get("ai_enabled")
    logger.info(f"No rule matched. ai_enabled={ai_enabled} ai_fallback={ai_fallback}")

    if ai_fallback == "true":
        logger.info("Calling Gemini...")
        ai_response = generate_response(phone, message, context)
        logger.info(f"Gemini response: '{str(ai_response)[:80]}'")
        if ai_response:
            log_message(phone, "out", ai_response, intent="ai")
            return ai_response

    response = config.get("unknown_message", "Não entendi. Pode reformular?")
    logger.info(f"Fallback -> unknown_message")
    log_message(phone, "out", response, intent="unknown")
    return response
