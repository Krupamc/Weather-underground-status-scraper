# Weather Underground Station Status Check:
## Features:
* This program checks if a station is online, offline, or in a error state. 
  * If a station is off (configerable) `3` times in a row, an email will be sent saying it went down.
  * If a station is online, nothing happens.
  * If a station is in a error/unknown state, it will not be counted in the 3 times to be off.
  * When stations come back online from being off, recovery emails will be sent
* If a station is in `maintenance` mode, no emails will be sent about it.
---
## Nerdy Features:
- Configurable thresholds, timing, and email configuration.
- CSV Logging of every event/log.
- Console summary of the runs/real time logging.
- File Auto-intializing (JSON, CSV, etc).
- Automatic report and email systems.
- Persistant per-station state in JSON
- HTTP, scraping, and general error handling.
---
## Emails:
### Recipients:
- Admin: Email(s) configured to recieve only system error emails
- Global Recipients: Email(s) configured to receive all emails sent by system concering status.
- Report Recipients: Email(s) configured to reveive monthly emails. E.g. Mesonet maintainers
- Station Recipients: Email(s) configured seperatly for each station. E.g. station owners.

### Types:
- Offline: Sent after a station is recorded off `3` (default) times in a row.
- Recovery: Sent once a station is detected to be online after being considered `offline`
- Reminder: Sent after `7` days (default) to remind of the status.
- Monthly Reports: Sent at the `first of the month at 8 AM` (default) with statitsics such as which stations had outages, the station with longest, uptime percentage for each station, etc.
- System Errors: Sent to system `admins` for any errors detected, HTTP, Requests, Time, etc.
---

# Config: How to use this system?
#### This system is fairly straight forward, create a venv with the packages (insert link to below packages), make a cron job (or similar scheduler) to run `scrape.py` in that venv every `10` mins or so (up to you).
(Picture tutorial soon to follow)
---

## Future:
- Other notification methods will be added if needed?
- Toggling a station maintenance mode using a FastAPI server?
---

### Packages used:
- Check requirements.txt

#### Commands for packages:
* pip install requirements.txt
