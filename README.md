# US Momentum Scanner – GitHub + Streamlit

## Sofort bereit
`app.py` liest die Ticker aus `data/*.txt` und scannt sie mit yfinance.

## Dateien
- `app.py`
- `requirements.txt`
- `generate_universe.py`
- `update_universe.bat`
- `data/sp500.txt`
- `data/nasdaq100.txt`
- `data/russell2000.txt`
- `data/all_unique.txt`

## GitHub
Alle Dateien hochladen. `app.py` muss im Hauptverzeichnis liegen.

## Streamlit Community Cloud
Repository auswählen → Branch `main` → Main file `app.py` → Deploy.

## Aktualisieren
Lokal `update_universe.bat` ausführen und die aktualisierten `data/*.txt` wieder nach GitHub hochladen.

Der Russell-Teil ist als IWM-Equity-Holdings-Proxy gekennzeichnet, weil ETF-Holdings nicht zwingend bytegenau der offiziellen Index-Mitgliederliste entsprechen.

Technische Screening-App, keine Anlageberatung.
