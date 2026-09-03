# CRYPTO-PRICE-BOT

Bot Telegram personale (uso esclusivo, nessun gruppo) per monitorare i prezzi
di un set fisso di criptovalute tramite CoinGecko API. Mostra snapshot dei
prezzi a comando, permette di impostare alert su soglie specifiche e invia
notifiche automatiche ogni volta che un prezzo attraversa un livello fisso.

## Token monitorati

Fissi, nessun comando per aggiungerne altri:

`BTC` · `ETH` · `XRP` · `SOL` · `LTC` · `AVAX`

## Funzionalità

### Comandi Telegram

| Comando | Descrizione |
|---|---|
| `/prezzo` | Snapshot dei prezzi correnti (EUR/USD) di tutti i token monitorati |
| `/alert_up SIMBOLO PREZZO VALUTA` | Alert quando il prezzo **sale sopra** la soglia (es. `/alert_up BTC 60000 USD`) |
| `/alert_down SIMBOLO PREZZO VALUTA` | Alert quando il prezzo **scende sotto** la soglia (es. `/alert_down ETH 2000 EUR`) |
| `/list` | Elenco degli alert attivi, numerati |
| `/remove NUMERO` | Rimuove l'alert al numero indicato (vedi `/list`) |
| `/quota` | Chiamate CoinGecko usate/rimanenti nel mese corrente |

Ogni comando risponde solo se inviato dalla chat autorizzata (`TELEGRAM_CHAT_ID`);
messaggi da altre chat vengono ignorati silenziosamente.

Gli alert seguono una logica "crossing": una volta impostati restano attivi
e notificano solo quando la soglia viene attraversata, non ad ogni ciclo in
cui la condizione resta vera.

> **Nota:** i comandi usano l'underscore (`/alert_up`, non `/alert-up`)
> perché Telegram non riconosce il trattino come parte del nome di un
> comando bot.

### Notifiche automatiche a step ("nuovo livello")

Oltre agli alert manuali, il job periodico (ogni 5 minuti) invia una
notifica automatica ogni volta che il prezzo di un token attraversa uno
step fisso — sia in salita 📈 che in discesa 📉 — controllato in modo
indipendente in EUR e in USD:

| Token | Step (EUR e USD) |
|---|---|
| BTC | 1.000 |
| ETH | 250 |
| SOL | 5 |
| XRP | 0,25 |
| AVAX | 0,50 |
| LTC | 2,5 |

Il calcolo: `livello = floor(prezzo / step)`. Se il livello cambia rispetto
all'ultimo salvato, parte la notifica. Non richiede configurazione: parte
da sola sui 6 token fissi. Lo stato (ultimo livello raggiunto per ciascun
token/valuta) è persistito in SQLite (tabella `step_state`), per evitare
notifiche duplicate o perse tra un riavvio e l'altro del bot.

## Consumo API CoinGecko

Il job periodico (ogni 5 minuti) usa la API key autenticata per una singola
chiamata batch che copre tutti i token monitorati e alimenta sia gli alert
che le notifiche a step (≈ 8.640 chiamate/mese su una quota di 10.000).

Le richieste on-demand dell'utente (`/prezzo`, creazione di un alert)
usano invece l'endpoint pubblico anonimo di CoinGecko, che **non consuma**
la quota mensile della API key — puoi chiederle liberamente. `/prezzo`
riusa comunque l'ultimo prezzo se richiamato entro 60 secondi.

## Struttura del progetto

```
CRYPTO-PRICE-BOT/
├── bot.py                    # comandi Telegram + job periodico (alert + step)
├── coingecko.py               # chiamate API CoinGecko, cache, contatore chiamate
├── db.py                       # accesso SQLite (alert, symbol mapping, quota, step)
├── formatter.py                 # formattazione dei messaggi Telegram
├── config.py                     # caricamento .env, costanti, step sizes
├── requirements.txt
├── crypto-price-bot.service        # unit file systemd per il deploy sulla VPS
├── .env.example                      # placeholder delle variabili richieste
└── .gitignore
```

## Setup locale

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # poi compilare con i valori reali
python bot.py
```

Variabili richieste in `.env`:

- `TELEGRAM_BOT_TOKEN` — token del bot da BotFather
- `TELEGRAM_CHAT_ID` — chat_id autorizzato (unica chat che riceve risposte)
- `COINGECKO_API_KEY` — API key CoinGecko piano Demo

Il database SQLite (`crypto.db`) viene creato automaticamente al primo
avvio nella cartella del progetto e non è incluso nel repo (vedi
`.gitignore`).

Nessuna porta di rete esposta: il bot usa long polling verso i server
Telegram, nessun webhook necessario.

Un file `crypto-price-bot.service` è incluso come esempio di unit file
systemd per chi vuole eseguire il bot come servizio in background su
Linux.
