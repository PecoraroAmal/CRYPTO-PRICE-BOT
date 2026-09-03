import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
COINGECKO_API_KEY = os.environ["COINGECKO_API_KEY"]

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crypto.db")

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

POLL_INTERVAL_SECONDS = 300
PRICE_CACHE_SECONDS = 60

# Step per notifica automatica di "nuovo livello" (stesso valore in EUR e USD)
STEP_SIZES = {
    "BTC": 1000,
    "ETH": 250,
    "SOL": 5,
    "XRP": 0.25,
    "AVAX": 0.50,
    "LTC": 2.5,
}
