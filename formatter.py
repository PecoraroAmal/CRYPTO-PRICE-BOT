from datetime import datetime, timezone

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€"}

DOT_EMOJI = {
    "BTC": "🟠",
    "ETH": "🔵",
    "SOL": "🟣",
    "LTC": "⚪",
    "XRP": "⚫",
    "AVAX": "🔴",
}
DEFAULT_DOT_EMOJI = "🔘"

DISPLAY_ORDER = ["BTC", "ETH", "XRP", "SOL", "LTC", "AVAX"]


def format_price(value: float) -> str:
    decimals = 0 if value >= 1000 else 2
    formatted = f"{value:,.{decimals}f}"
    # swap to European style: "," thousands -> ".", "." decimals -> ","
    formatted = formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return formatted


def format_amount(value: float, currency: str) -> str:
    return f"{format_price(value)}{CURRENCY_SYMBOLS[currency]}"


def _display_sort_key(symbol: str) -> tuple:
    if symbol in DISPLAY_ORDER:
        return (0, DISPLAY_ORDER.index(symbol))
    return (1, symbol)


def format_prezzo(prices: dict, symbol_to_id: dict[str, str]) -> str:
    lines = ["💰 *Prezzi Attuali*", ""]
    for symbol in sorted(symbol_to_id, key=_display_sort_key):
        coingecko_id = symbol_to_id[symbol]
        entry = prices.get(coingecko_id)
        if not entry:
            continue
        eur = format_amount(entry["eur"], "EUR")
        usd = format_amount(entry["usd"], "USD")
        emoji = DOT_EMOJI.get(symbol, DEFAULT_DOT_EMOJI)
        lines.append(f"{emoji} {symbol}: {eur} / {usd}")
    return "\n".join(lines)


def format_alert_set(symbol: str, direction: str, threshold: float, currency: str) -> str:
    arrow_emoji = "🟢" if direction == "up" else "🔴"
    word = "sopra" if direction == "up" else "sotto"
    return (
        "✅ *Alert impostato*\n"
        f"{arrow_emoji} {symbol} {word} {format_amount(threshold, currency)}"
    )


def format_list(alerts: list) -> str:
    if not alerts:
        return "📋 *Alert attivi*\n\nNessun alert impostato."
    lines = ["📋 *Alert attivi*", ""]
    for i, alert in enumerate(alerts, start=1):
        arrow_emoji = "🟢" if alert["direction"] == "up" else "🔴"
        word = "sopra" if alert["direction"] == "up" else "sotto"
        amount = format_amount(alert["threshold"], alert["currency"])
        lines.append(f"{i}. {arrow_emoji} {alert['symbol']} {word} {amount}")
    lines.append("")
    lines.append("Usa /remove <numero> per rimuoverne uno")
    return "\n".join(lines)


def format_alert_triggered(symbol: str, direction: str, threshold: float, currency: str, current_price: float) -> str:
    word = "superato" if direction == "up" else "sceso sotto"
    return (
        "🔔 *Alert scattato!*\n\n"
        f"{symbol} ha {word} {format_amount(threshold, currency)}\n"
        f"Prezzo attuale: {format_amount(current_price, currency)}"
    )


def format_quota(used: int, monthly_limit: int) -> str:
    remaining = monthly_limit - used
    now = datetime.now(timezone.utc)
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1)
    else:
        next_month = now.replace(month=now.month + 1)
    month_names = [
        "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    ]
    reset_label = f"1° {month_names[next_month.month - 1]}"
    return (
        "📊 *Quota CoinGecko*\n\n"
        f"Usate questo mese: {used:,}".replace(",", ".") + f" / {monthly_limit:,}".replace(",", ".") + "\n"
        f"Rimanenti: {remaining:,}".replace(",", ".") + "\n"
        f"Reset: {reset_label}"
    )


def format_step_notification(symbol: str, currency: str, direction: str, current_price: float) -> str:
    trend_emoji = "👆🏼" if direction == "up" else "👇🏼"
    return f"{trend_emoji} *{symbol}*: livello raggiunto {format_amount(current_price, currency)}"


def format_help() -> str:
    return (
        "ℹ️ *Comandi disponibili*\n\n"
        "💰 `/prezzo`\n"
        "Mostra i prezzi attuali di tutti i token (EUR/USD).\n\n"
        "🟢 `/alert_up SIMBOLO PREZZO VALUTA`\n"
        "Avvisa quando il prezzo SALE sopra la soglia.\n"
        "Esempio: `/alert_up BTC 60000 USD`\n\n"
        "🔴 `/alert_down SIMBOLO PREZZO VALUTA`\n"
        "Avvisa quando il prezzo SCENDE sotto la soglia.\n"
        "Esempio: `/alert_down ETH 2000 EUR`\n\n"
        "SIMBOLO: BTC, ETH, XRP, SOL, LTC o AVAX\n"
        "VALUTA: EUR o USD (va sempre indicata)\n\n"
        "📋 `/list`\n"
        "Mostra gli alert attivi, numerati.\n\n"
        "🗑 `/remove NUMERO`\n"
        "Elimina un alert. Il NUMERO è quello mostrato da `/list`.\n"
        "Esempio: prima `/list`, poi `/remove 2` per eliminare il secondo.\n\n"
        "📊 `/quota`\n"
        "Chiamate CoinGecko usate/rimanenti questo mese.\n\n"
        "In più, ogni token ha delle notifiche automatiche ogni volta che "
        "il prezzo attraversa un livello fisso (es. BTC ogni 1.000$/€, "
        "ETH ogni 250, ecc.) — nessun comando richiesto, partono da sole.\n\n"
        "Token - Step"
        "BTC - 1.000"
        "ETH - 250"
        "SOL - 5"
        "XRP - 0,25"
        "AVAX - 0,50"
        "LTC - 2,5"
    )
