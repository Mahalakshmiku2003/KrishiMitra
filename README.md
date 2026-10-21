to run the project:
1st terminal:
(venv) PS C:\Krishi-Mitra> cd backend
(venv) PS C:\Krishi-Mitra\backend> python -m venv venv
>> venv\Scripts\activate
(venv) PS C:\Krishi-Mitra\backend>  uvicorn main:app --reload --port 8000

this is what you should get:

INFO:     Will watch for changes in these directories: ['C:\\Krishi-Mitra\\backend']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [8096] using WatchFiles
✅ Tools loaded: 33 diseases, 15 mandis
✅ Disease DB loaded: 33 entries
✅ Progression DB loaded: 22 entries
INFO:     Started server process [2564]
INFO:     Waiting for application startup.
✅ Database tables verified
[Scheduler] Started. Registered jobs:
  outbreak_monitor → next run: 2026-10-21 10:38:50.607790+05:30
  price_alerts_job → next run: 2026-10-21 11:00:00+05:30
  daily_price_fetch → next run: 2026-10-22 00:00:00+05:30
  morning_briefing_job → next run: 2026-10-22 07:00:00+05:30
  daily_karnataka_scrape → next run: 2026-10-22 10:20:00+05:30
🚀 Scheduler started
INFO:     Application startup complete

2nd terminal:
PS C:\Krishi-Mitra> cd backend
PS C:\Krishi-Mitra\backend> python -m venv venv
>> venv\Scripts\activate
PS C:\Krishi-Mitra> ngrok http 8000

this is what you should get:

Session Status                online                                                                               Session Expires             Mon, 26 Oct 2026 01:02:16 +0530
Version                     3.8.0                                                                                Version                     3.8.0
Region                      India (in)                                                                           Region                      India (in)
Web Interface               http://localhost:4040                                                                Web Interface               http://localhost:4040
Forwarding                  https://chemoreceptive-carolina-undestructibly.ngrok-free.dev -> http://localhost:8000
Forwarding                  https://chemoreceptive-carolina-undestructibly.ngrok-free.dev -> http://localhost:8000

Connections                   ttl     opn     rt1     rt5     p50     p90
