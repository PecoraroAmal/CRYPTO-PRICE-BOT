import functools
import logging
import math

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes

import coingecko
import db
import formatter
from config import POLL_INTERVAL_SECONDS, STEP_SIZES, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger("crypto-price-bot")

MONTHLY_API_LIMIT = 10_000
VALID_CURRENCIES = {"EUR", "USD"}


def authorized_only(handler):
    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id != TELEGRAM_CHAT_ID:
            logger.warning("Messaggio ignorato da chat non autorizzata: %s", chat_id)
            return
        result = await handler(update, context)
        try:
            await update.message.delete()
        except Exception:
            logger.warning("Impossibile eliminare il messaggio comando", exc_info=True)
        return result

    return wrapper


def _symbol_to_id_map() -> dict[str, str]:
    return {row["symbol"]: row["coingecko_id"] for row in db.list_symbol_mappings()}


@authorized_only
async def cmd_prezzo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol_to_id = _symbol_to_id_map()
    prices = coingecko.get_prices_cached(list(symbol_to_id.values()))
    await update.message.reply_text(
        formatter.format_prezzo(prices, symbol_to_id), parse_mode="Markdown"
    )


async def _parse_alert_args(update: Update, args: list[str]):
    if len(args) != 3:
        await update.message.reply_text(
            "Uso: /alert_up SIMBOLO PREZZO VALUTA (es. /alert_up BTC 60000 USD)"
        )
        return None
    symbol, price_str, currency = args
    symbol = symbol.upper()
    currency = currency.upper()

    if db.get_coingecko_id(symbol) is None:
        await update.message.reply_text(f"Simbolo sconosciuto: {symbol}")
        return None
    try:
        threshold = float(price_str.replace(",", "."))
    except ValueError:
        await update.message.reply_text(f"Prezzo non valido: {price_str}")
        return None
    if currency not in VALID_CURRENCIES:
        await update.message.reply_text("Valuta non valida: usa EUR o USD")
        return None
    return symbol, threshold, currency


async def _handle_alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE, direction: str):
    parsed = await _parse_alert_args(update, context.args)
    if parsed is None:
        return
    symbol, threshold, currency = parsed

    coingecko_id = db.get_coingecko_id(symbol)
    prices = coingecko.get_prices_cached([coingecko_id])
    current_price = prices[coingecko_id][currency.lower()]
    current_state = "above" if current_price >= threshold else "below"

    db.add_alert(symbol, direction, threshold, currency, current_state)
    await update.message.reply_text(
        formatter.format_alert_set(symbol, direction, threshold, currency),
        parse_mode="Markdown",
    )


@authorized_only
async def cmd_alert_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_alert_command(update, context, "up")


@authorized_only
async def cmd_alert_down(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_alert_command(update, context, "down")


@authorized_only
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alerts = db.list_alerts()
    await update.message.reply_text(formatter.format_list(alerts), parse_mode="Markdown")


@authorized_only
async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Uso: /remove NUMERO (vedi /list)")
        return
    try:
        position = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Numero non valido.")
        return
    if db.remove_alert_by_position(position):
        await update.message.reply_text(f"🗑 Alert #{position} rimosso.")
    else:
        await update.message.reply_text("Numero non trovato in /list.")


@authorized_only
async def cmd_quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    used = db.get_api_usage()
    await update.message.reply_text(
        formatter.format_quota(used, MONTHLY_API_LIMIT), parse_mode="Markdown"
    )


@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(formatter.format_help(), parse_mode="Markdown")


async def _check_step_levels(context: ContextTypes.DEFAULT_TYPE, symbol_to_id: dict, prices: dict):
    for symbol, coingecko_id in symbol_to_id.items():
        step = STEP_SIZES.get(symbol)
        entry = prices.get(coingecko_id)
        if step is None or not entry:
            continue
        for currency in ("EUR", "USD"):
            price = entry[currency.lower()]
            bucket = math.floor(price / step)
            last_bucket = db.get_step_bucket(symbol, currency)
            if last_bucket is None:
                db.set_step_bucket(symbol, currency, bucket)
                continue
            if bucket != last_bucket:
                direction = "up" if bucket > last_bucket else "down"
                db.set_step_bucket(symbol, currency, bucket)
                text = formatter.format_step_notification(symbol, currency, direction, price)
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")


async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    symbol_to_id = _symbol_to_id_map()
    if not symbol_to_id:
        return
    try:
        prices = coingecko.fetch_prices(list(symbol_to_id.values()))
    except Exception:
        logger.exception("Errore durante il fetch prezzi periodico")
        return

    await _check_step_levels(context, symbol_to_id, prices)

    for alert in db.list_alerts():
        coingecko_id = symbol_to_id.get(alert["symbol"])
        if coingecko_id is None or coingecko_id not in prices:
            continue
        current_price = prices[coingecko_id][alert["currency"].lower()]
        new_state = "above" if current_price >= alert["threshold"] else "below"

        crossed_up = alert["direction"] == "up" and alert["current_state"] == "below" and new_state == "above"
        crossed_down = alert["direction"] == "down" and alert["current_state"] == "above" and new_state == "below"

        if new_state != alert["current_state"]:
            db.update_alert_state(alert["id"], new_state)

        if crossed_up or crossed_down:
            text = formatter.format_alert_triggered(
                alert["symbol"], alert["direction"], alert["threshold"], alert["currency"], current_price
            )
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")


BOT_COMMANDS = [
    BotCommand("prezzo", "Prezzi attuali di tutti i token"),
    BotCommand("alert_up", "Alert quando il prezzo sale sopra una soglia"),
    BotCommand("alert_down", "Alert quando il prezzo scende sotto una soglia"),
    BotCommand("list", "Elenco alert attivi"),
    BotCommand("remove", "Rimuove un alert (numero da /list)"),
    BotCommand("quota", "Chiamate CoinGecko usate/rimanenti"),
    BotCommand("help", "Guida ai comandi"),
]


async def _post_init(application: Application):
    await application.bot.set_my_commands(BOT_COMMANDS)


def main():
    db.init_db()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(_post_init).build()

    application.add_handler(CommandHandler("prezzo", cmd_prezzo))
    application.add_handler(CommandHandler("alert_up", cmd_alert_up))
    application.add_handler(CommandHandler("alert_down", cmd_alert_down))
    application.add_handler(CommandHandler("list", cmd_list))
    application.add_handler(CommandHandler("remove", cmd_remove))
    application.add_handler(CommandHandler("quota", cmd_quota))
    application.add_handler(CommandHandler("help", cmd_help))

    application.job_queue.run_repeating(check_alerts_job, interval=POLL_INTERVAL_SECONDS, first=POLL_INTERVAL_SECONDS)

    logger.info("Bot avviato, in polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
