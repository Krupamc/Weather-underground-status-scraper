# Weather Underground Station Status Check:

## Tables of Contents

- [Why did I create this?](#why-did-i-create-this)
- [What is this?](#what-is-this)
  - [Weather and Status Scrapers](#weather-and-status-scrapers)
  - [Backend](#backend)
  - [Frontend (website)](#frontend-website)
- [Status Scraper Monitoring and Notifications](#status-scraper-monitoring-and-notifications)
- [Weather Scraper](#weather-scraper)
- [System Website](#system-website)
  - [Types of Users](#types-of-users)
  - [Public Dashboards](#public-dashboards)
  - [Admin Dashboards](#admin-dashboards)
  - [Graphing and Analysis](#graphing-and-analysis)
    - [Graphing](#graphing)
    - [Varaiable Analysis](#variable-analysis)
    - [Tests](#tests)
      - [Linear Regressions](#tests)
      - [T-Test](#tests)
      - [ANOVA](#tests)
  - [Login](#login-page-disapears-from-the-bar-once-logged-in)
  - [Register](#register-page-disapears-from-the-bar-once-logged-in)
  - [My Stations](#my-stations)
  - [Settings Page](#settings-page-if-admin)
  - [Logout](#logout)
- [Nerdy Features](#nerdy-features)
- [Future Work](#future-work)
- [Notes](#notes)
- [Setup](#setup)

## Why did I create this?
Hey! My name is Krupam, and I am a nerd. If you are reading this, you are most likely one as well. I love weather, and learning about it. Other people who love weather will create and host Personal Weather Stations (PWS) and post the data to websites like [Weather Underground](https://www.wunderground.com). I have used these stations for my own research projects. [Check one out!](https://github.com/Krupamc/Research-2026-LSTM). In my area, there is a mesonet (regional network of PWS's) from the [Save Barnegat Bay non-profit (check them out, they are awesome!)](https://savebarnegatbay.org/). I have used plenty of their stations in my research. I was given the amazing opportunity to present my research at one of their meetings regarding their mesonet. It was eye-opening! As I listened into the meeting, they discussed one of the current issues; they could never tell when a weather station went down. The station owners would find out days after if not weeks. This program is the solution to that and more.
---

## What is this?
The system is a weather-station data platform and monitoring system. The system collects data from Weather Underground (WU), turns it into usable information, and alerts station owners and administrators when a station needs attention. All data is shown on the website in a easy, user-friendly approach. This includes dashboards, graphing, analysis, scientific tests, and admin controls (accessed through JWT-based auth). The system is coded mostly in Python and there are three main systems: The weather and status scrapers, backend, and frontend website.
<img width="2531" height="1260" alt="image" src="https://github.com/user-attachments/assets/19c0c082-6ad8-4827-95d2-876ff7b04890" />

To see more in depth `Devlogs` of me working through the project, check out my [Stardance project](https://stardance.hackclub.com/projects/30441) page.

### Weather and Status Scrapers:
Automated programs that check WU for each registered station's latest weather data and offline/online status. Because of WU deprecating their free API, this project reads data from the public dashboard. This uses the Python library `BeautifulSoup` as well as `Requests` and other libraries. These scrapers gets the list of stations to scrape by pulling the list from the backend `FastAPI` server API.

### Backend:
Behind-the-scenes of the website. It receives data from the scrapers, stores, performs calculations, conversions, managing of station settings and permissions, as well as alerts and reports. The backend is built using the `FastAPI` library as well as `Jinja2` templates to serve the frontend.

### Frontend (website):
The public-facing website. It presents the station data in a clear, user-friendly way through station pages,dashboards, weather widgets, graphs, and analysis tools. It serves up HTML pages with `Jinja2` as well as custom CSS, as well as other features. It includes plenty of user-friendly features. 
---

## Weather Scraper:
Scrapes the weather values for all stations and converts them to metric values and the collected time into UTC before posting it to the backend API. The values are also stored in monthly CSVs. Only stations that have the `collect_enabled` value in the database are scraped. Only the latest weather reading is kept in the live table; every reading is also appended to WeatherHistory.

## Status Scraper Monitoring and Notifications:
Scrapes the stations for their status and converted the collected time into UTC and posts it to the backend API. The values are stored in a csv. When the backend receives it, it is used in the Status column (rewritten every new status) and only saved to the StatusHistory column when the status changes. Only stations that have the `collect_enabled` value in the database are scraped.

* This program checks if a station is online, offline, or in an error state. 
  * If a station is off (configurable) `3` times in a row, an email will be sent saying it went down.
  * If a station is online, nothing happens.
  * If a station is in an error/unknown state, it will not be counted in the 3 times to be off.
  * When stations come back online from being off, recovery emails will be sent
* If a station is in `maintenance` mode, no emails will be sent about it. Admin Accounts in the Frontend can toggle this setting.
<img width="1086" height="287" alt="image" src="https://github.com/user-attachments/assets/7e913b7e-2f22-4dfe-83fb-88a4e10e28e7" />

### Emails:
#### Recipients:
- Admin: Email(s) configured to receive only system error emails
- Global Recipients: Email(s) configured to receive all emails sent by system concerning status.
- Report Recipients: Email(s) configured to receive monthly emails. E.g. Mesonet maintainers
- Station Recipients: Email(s) configured separately for each station. E.g. station owners.

#### Types:
- Offline: Sent after a station is recorded off `3` (default) times in a row.
- Recovery: Sent once a station is detected to be online after being considered `offline`
- Reminder: Sent after `7` days (default) to remind of the status.
- Monthly Reports: Sent at the `first of the month at 8 AM` (default) with statistics such as which stations had outages, the station with longest, uptime percentage for each station, etc.
- System Errors: Sent to system `admins` for any errors detected, HTTP, Requests, Time, etc.
<img width="1022" height="752" alt="image" src="https://github.com/user-attachments/assets/651f0da9-a089-4827-828e-20b80f98c84d" />


---

## System Website:
I originally created this website just to toggle maintenance mode on the stations, however it ended up becoming a way for the public to interact with the stations and their data as well. This approach is lot more user-friendly and easier than using WU for the mesonet. Custom CSS is used everywhere for animations, colors, etc. A station list allows anyone to look at public dashboard with widgets, downloadable reports, CSVs, graphs, general statistics, scientific tests (such as T-tests, ANOVA, and linear regressions), and more!

#### Types of Users:
- General Public (no login required), who can view public dashboards, explore trends, etc.
- Administrators and maintenance staff, who can manage stations, receive outage alerts, monitor station health, and more.

Different accounts can be created on the website (using `JWT-based session authentication`) with the default `public` role. Admins accounts can then assign stations to that account to give them access to stations. This includes toggling maintenance mode and turning off the public dashboard for that station. Admin accounts can also toggle the public dashboard for everyone. When a user logs in, they are redirected to the `my-station` page. If they have no stations, it says so in a pop-up, otherwise a list of stations is shown. Admin accounts have access to all stations.

### 4XX Errors:
There are dedicated 400, 401, 403, 404, and 500 (currently not working) error pages. There is a global exception handler to send users here with the error message attached and shown. There is also a button to be sent back to the home page (or log in for the 401).
<img width="2347" height="643" alt="image" src="https://github.com/user-attachments/assets/4d76514b-63c3-4f3a-86da-89d8357c0f7f" />

### Navigation Bar:
Links to pages. Logo nav item sends the user back to the home page.
<img width="1731" height="232" alt="image" src="https://github.com/user-attachments/assets/946c23fd-b86d-41b1-8471-978163cec306" />

### Weather Stations:
Lists all of the stations (with public dashboards enabled) as a button link to their public dashboards.
<img width="1822" height="1267" alt="image" src="https://github.com/user-attachments/assets/6bafcefa-ca8a-4c46-9eaa-b5dfa03cb9f8" />

### Public Dashboards:
There are dashboard for each station (that has the dashboard enabled) that hold the current status and weather values and shows the values through widgets and images. The current status is shown through a online/offline text and image. When clicked it takes you to the orginal WU page. There are buttons to view the page with imperial or metric units (through query parameters). If there is no data, the dashboard is disabled, or offline, the dashboard has a pop-up saying `Station not Available`.
<img width="2530" height="1258" alt="image" src="https://github.com/user-attachments/assets/c1990ce3-9833-46f4-9ade-e69d37911262" />

#### Widgets:
- Air Temperature: Thermometer that fills based on the temperature.
- Pressure: Barometer that changes based on the pressure.
- Wind: Wind Direction is shown with a compass and an arrow pointing where the wind flows. Also says the speed and gust in text.
<img width="598" height="365" alt="image" src="https://github.com/user-attachments/assets/0d2e2711-0863-412b-87e0-c17e3dbcf544" />

#### Static:
- Dew Point/Humidity
- Precipitation Rate/Precipitation Accumulation
- UV Index/Solar Radiation (if that station measures them)
<img width="1692" height="270" alt="image" src="https://github.com/user-attachments/assets/73364cfe-585f-4451-9f67-59f575acc638" />

#### Graphs:
Graphs are shown of the last 24 hours of data. These include:
- Air Temperature, Dew Point, Humidity
- UV Index, and Solar Radiation (if that station measures them)
- Pressure
- Wind Speed and Gusts
<img width="1642" height="795" alt="image" src="https://github.com/user-attachments/assets/beddfa13-aeae-4e52-9d41-0840a2fdd9af" />

#### Table:
The table at the bottom shows all variables (if they are available) and all their values for that day. Using the `Next Day` and `Previous Day`, you can easily navigate between data. You can also navigate to a specific day with a date input and `Go` button. All data can be downloaded as a CSV.
<img width="2447" height="1277" alt="image" src="https://github.com/user-attachments/assets/9b256683-59f4-4212-9b3e-077afb1ce4e2" />

### Admin Dashboards:
Contains all features (except for the data table) in the [Public dashboard](#public-dashboards) as well as some extras.
<img width="2487" height="1207" alt="image" src="https://github.com/user-attachments/assets/2ffd7030-1a04-4eab-96d0-3795d7cf9a21" />

- Maintenance Mode and Public Dashboard Toggles: The buttons toggles the status (and show a pop-up of success!) and then change color. If a station is put into maintenance mode, the public dashboard is turn off and cannot be turned back on till maintenance mode is over. The public dashboard does not affect maintenance mode however. The toggles can only be used if the user has access to toggle them (separate permission).
<img width="1688" height="695" alt="image" src="https://github.com/user-attachments/assets/e3185534-28ec-4fb5-a560-96ab2dd383a0" />

- Status Widget:
  - On:
    - Displays a green checkmark
    - Time of status
    - Name of last status ("CONNECTED")
      <img width="587" height="277" alt="image" src="https://github.com/user-attachments/assets/1eeb4122-99ce-43b4-ba0c-f5e71f48a921" />

  - Off:
    - Displays a red X
    - Time of status
    - Name of last status (usually "OFFLINE")

    In a separate widget with a gear icon:
    - Consecutive Offline (how many checks have occured with offline status)
    - First time offline
    - Last time Connected
    - If a alert email was sent about it
<img width="1163" height="485" alt="image" src="https://github.com/user-attachments/assets/51980f80-a995-4936-ae13-1cd36282b3a4" />

### Graphing and Analysis:
Holds HTML forms on seperate `tabs` to run different tests, graphs, etc.
<img width="2530" height="1258" alt="image" src="https://github.com/user-attachments/assets/fda46f2c-1f82-4b87-a304-2c6a04a218c7" />

#### Graphing:
Generates a MatPlotLib Graph
Inputs:
- Selected Station (from list of public station)
- Graph Title (text)
- Range Mode: Relative Range (ex: past `3` `hours`) or Date Range (ex: 7/7/2026 - 7/9/2026)

If relative range:
  - Relative Range
    - Number of...
    - Select hours, days, weeks, months, or years
  - Range Presets: (24 hours, past week, past month, past 6 months, past year)

If date range:
  - Date Range
    - Start date
    - End date
  - Date Presets: (Today, last week, last month, last 6 months, last year)

- Variable Presets:
  - Temperature (Air Temperature, Dew Point, and Humidity)
  - Wind (Wind Speed and Gusts)
  - Precipiatation (Rate and Accumulation)
  - Pressure
  - Solar (UV index and solar radiation)
  - Clear

- Variables:
  - Air Temperature
  - Dew Point
  - Humidity
  - Pressure
  - Wind Speed
  - Wind Gust
  - Wind Direction
  - Precipitation Rate
  - PrecipItation Accumulation
  - UV Index
  - Solar Radiation

- Units (imperial or metric)
<img width="957" height="1035" alt="image" src="https://github.com/user-attachments/assets/3bb6d223-00a6-4337-96a3-83b3d9a16623" />

Output:
Graph generated with MatPlotLib.
When a graph is generated, the download graph (as png) and download CSV buttons appear. Until then, a `No Graph Yet` widget
<img width="2512" height="1210" alt="image" src="https://github.com/user-attachments/assets/a1d2c95e-71fa-41ee-a722-6e6eae4d69b5" />

#### Variable Analysis
Perform analysis over a range of time.

Inputs:
- Selected Station (from list of public station)
- Variable
- Range Mode

- Same inputs/presets for range mode
- Units (imperial or metric)
<img width="2526" height="1247" alt="image" src="https://github.com/user-attachments/assets/41e54d74-e227-4994-9fcb-c0cb23fd28c8" />

Outputs:
A widget is shown with the results and the ability to download a csv of the results and all of the data used to generate it:
- Latest Value
- Min
- Max
- Mean
- Median
- Range
- Sample Size (n value)
- Trend (Rising, falling, or settle with a trend arrow image that is appropriate)
In a seperate `Coverage` widget:
- Start time
- End time
- Units
<img width="1468" height="927" alt="image" src="https://github.com/user-attachments/assets/fa5c72e2-e794-43d2-add7-304631b0d4bb" />


#### Tests:
Performs a scientific test. Linear Regressions (LR), One-Way ANOVA, Independent Two Sample T-Test.
<img width="2435" height="1185" alt="image" src="https://github.com/user-attachments/assets/fc40b437-d84a-49c6-8541-5fad62151a73" />

Inputs:
- Selected Test (from above)

If LR:
  - Selected Station (from list of public station)
  - X variable
  - y variable
  - LR Graph Title
<img width="1222" height="567" alt="image" src="https://github.com/user-attachments/assets/7a30ddd4-035f-4448-b81d-a7301506bed1" />

If T-Test:
  - Variable
  - Station A (from list of public station)
  - Station B (from list of public station)
<img width="1205" height="456" alt="image" src="https://github.com/user-attachments/assets/e4942af3-52eb-4a48-adc1-f01106112d85" />

If ANOVA:
  - Variable
  - Station A (from list of public station)
  - Station B (from list of public station)
  - Station C (from list of public station)
<img width="1206" height="587" alt="image" src="https://github.com/user-attachments/assets/bd9e380c-d475-4702-bdbb-0e727aa3693f" />

- Same inputs/presets for range mode
- Units (imperial or metric)

Output:
If LR:
Graph generated with MatPlotLib.
When a graph is generated, the download graph (as png) and download CSV buttons appear.
<img width="1255" height="497" alt="image" src="https://github.com/user-attachments/assets/a7d2e42c-501d-46fc-9770-71c588cad56f" />

If T-Test:
A widget is shown with the P-Value and the Test Statstic.
<img width="1343" height="477" alt="image" src="https://github.com/user-attachments/assets/cb7e3f2c-69f3-4b08-8849-002972a19980" />

If ANOVA:
A widget is shown with the P-Value and the F-Statstic.
<img width="1267" height="445" alt="image" src="https://github.com/user-attachments/assets/7f950bf6-d8a4-4589-b52b-6eb5fbe7fdd5" />

### Login (page disapears from the bar once logged in):
HTML form that allows the user to input their username and password and press sign in. If either is incorrect, the form responds with a `Invalid Credentials` error. There is a `Forgot your password?` button that tells you to send the admin a email and a `Did you mean to register?` button to send you to the register page. This login uses JWT-based session authentication. A 30-minute access cookie is given to the browser.
<img width="1247" height="873" alt="image" src="https://github.com/user-attachments/assets/5f30430a-22c6-47be-9e8d-76b58d5b68c4" />

### Register (page disapears from the bar once logged in):
Enter your username and password. A public account will be created and the user will be forwarded to the `My Stations` page. I might disable this for the time being and allow only users to be created in the [admin settings page](#settings-page-if-admin) until I make features for a public account user to use. The first account created is an admin account.

#### Username Safety:
- Min length: 3
- Max length: 15
- Type: Letters and numbers
- Allows username saving/autocomplete

#### Password Safety:
- Min length: 12
- Max length: 64
- Pattern: Requires lower, upper, digit, and special
- Allows username saving/autocomplete
<img width="787" height="582" alt="image" src="https://github.com/user-attachments/assets/815663f0-bca5-49e3-bfc6-13d3962cd1dd" />


### The rest of these pages are for logged in users.

### My Stations
Lists all station the user can view. Admins can see (and modify!) all stations.
<img width="1432" height="977" alt="image" src="https://github.com/user-attachments/assets/0c471a70-385b-4715-b8b7-af4cfcbcce0c" />

### Settings Page (if admin):
This is a Admin only page (in nav bar when admin) that configures, deletes, creates, the main functionalities. This includes stations and users. After every function is run, an error/success message show with detailed information depending on the function.
<img width="2532" height="1250" alt="image" src="https://github.com/user-attachments/assets/8b916215-5ded-4c24-9b34-d38c97b6029d" />

These Functions include:
- Modify User: Change role, username, password
- Register User: Create
- Delete User
- Read User Assigned Stations: Choose a station, the page reloads and show all stations the user can access.
- Grant User Access: Choose a user, and give them access to a station. This is view only by default
- Revoke Access: Remove User access to a specific station. On reload after choosing a user it shows any assigned stations
- Update User Access: Choose a user, on reload it shows all available stations and when selected, shows what access it has. You then check/uncheck the access you want it to have and submit.
- Modify Station: Currently only allows to change station name.
- Create Station: Enter new id and name as well as options to be public and in maintenance mode (default off).
- Delete Station: Deletes station only from the current stations. Does not delete data. I need to rewrite this to make it so it stops collecting data instead. The feature is designed but not finished.
- Read all Stations: Lists all stations and if they are in maintenance or not.
<img width="1242" height="983" alt="image" src="https://github.com/user-attachments/assets/dbaf9b41-a71c-40e5-a934-10221c4c94d6" />
<img width="1275" height="858" alt="image" src="https://github.com/user-attachments/assets/63a38782-193b-481b-816b-5cff977e74c9" />
<img width="1318" height="782" alt="image" src="https://github.com/user-attachments/assets/71419a5a-bd88-4ca1-a9ba-b6f96f30dce4" />

### Logout
Deletes browser cookie and logs out from website.

### Profile and Name:
A blank profile (generic empty user) shows up next to your username. Pressing it sends you to the `My Stations` Page
<img width="303" height="112" alt="image" src="https://github.com/user-attachments/assets/2f07d8f5-fb1b-417c-a8e2-ef53f1da05ba" />

## Nerdy Features:
- Configurable thresholds, timing, and email configuration.
  - Email Cooldowns: Error Emails have a cooldown as to not "spam" any admins with emails.
- CSV Logging of every event/log.
- Console summary of the runs/real time logging.
- File Auto-intializing (JSON, CSV, etc).
- Automatic report and email systems.
- Persistant per-station state in JSON
- HTTP, scraping, and general error handling.
- SQLite Database with autogenerated database.db
- Auto-synced new stations into `status.json` by calling backend API.
- Retry and backoff logic for all scraping calls.
- When scraping, all values are converted into metric values before being converted back based on the situation.
- The database has all times as UTC due to SQLite not storing Z data.
- Find the easter egg(s) I have littered around...
- The Seed endpoint creates stations based on the config file. It creates any not already in the database.
- All internal APIs use typed Pydantic/SQLModel response models for validated JSON responses.
- PWA Support (Can be installed as a PWS on phones/desktop),
- All times are stored in database as UTC. When served in the frontend, they are converted into whatever timezone is specified in the config.
- Can view and can toggle maintenance are seperate permissions for a user having access for a station.
## Future Work:
- More notification types. Ex: SMS
- Make Mobile Site Easier to navigate
- Docker container/compose deployment
- Get status and weather scrapers to use enviroment variables
- Right now, the config is used as the source of truth, will transition into the database being this.
- Create a Mailing list to send out weather reports
- Role is currently a plain string field, not a strict enum.

## Notes:
This is my first time ever using FastAPI, Jinja, HTML (properly), CSS, and JS. I apologise for any bugs/weird behavior :D.

# Setup
## This system is fairly straight forward, create a venv with the packages (insert link to below packages), make a cron job (or similar scheduler) to run `scrape.py` and `status.py` in that venv every `5` mins or so (up to you).
- `python -m venv venv`
- `source venv/bin/activate   # or venv\Scripts\activate on Windows`

(Picture tutorial coming soon)
---

### Packages used:
- Check requirements.txt

#### Commands for packages:
Install Packages:
- `pip install -r requirements.txt`
