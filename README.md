# TREMOR: a seismograph for the web

Watches public web pages and tells you when they meaningfully change.

**Status: Step 1 of 8 (core engine).** Add a URL, render it in a headless browser,
save the text and a screenshot, and store a new snapshot only when the content changes.

## Run it on a computer

```
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac / Linux
pip install -r requirements.txt
playwright install chromium
python server.py
```

API at http://localhost:8000. Tests: `python -m unittest test_core -v`

## API

| Method | Path | What it does |
|---|---|---|
| POST | /api/monitors | add a monitor (name, url, interval_min 15..1440) |
| GET | /api/monitors | list monitors with status, last checked, last changed |
| DELETE | /api/monitors/:id | remove a monitor |
| POST | /api/monitors/:id/check | check now |
| GET | /api/monitors/:id/snapshots | version history |
| GET | /api/monitors/:id/checks | every check, changed or not |
| GET | /shots/:monitor/:snapshot.png | screenshot |

## Design decisions

- An outage or CAPTCHA is not a change. 5xx and timeouts are `error`, 403/429 and CAPTCHA pages are `blocked`. No snapshot is stored.
- Public pages only, no stored credentials. Private and local addresses are rejected, also after redirects.
- Snapshots are stored only on change. Whitespace-only differences do not count.
