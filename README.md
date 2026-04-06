# Trip Canvas (Django)

A basic travel-planner web app built with Django where users can:
- Sign up, log in, and log out
- Create trips with destination, dates, budget, and interests
- View trip details
- Search destinations and save latitude/longitude for map use
- View an embedded map with destination and saved places markers
- Save attractions, restaurants, hotels, and other places for a trip
- Draw a simple route line between selected saved points
- Add itinerary items manually
- Add and track planning checklist items (hotel, train/transport tickets, visa/documents, packing, other)
- Get weather-aware planning suggestions based on season and interests
- View live current weather for mapped destinations
- See a 5-day forecast with rain chance and temperature windows
- Receive weather warning banners (rain, storm, heat, cold)
- Get smart day-shifting recommendations for outdoor sightseeing
- Generate AI-assisted day-wise itineraries using destination, days, budget, travel style, weather, preferred times, and saved places
- View AI output with morning/afternoon/evening suggestions, rough budget split, and packing guidance
- Save AI output back into the Itinerary & Budget tab as one itinerary item per generated day
- Uses a live OpenAI model when `OPENAI_API_KEY` is set, and falls back to the built-in planner when it is not available

## Tech Stack
- Python 3.11
- Django 5
- SQLite (default)

## Project Structure
- `travel_planner/` Django project settings and root urls
- `trips/` app with models, forms, views, urls, and helper logic
- `templates/` shared and app templates
- `manage.py` Django management entry point

## Setup
1. Open a terminal in the project root.
2. Create a virtual environment:

```powershell
python -m venv .venv
```

3. Activate the virtual environment:

Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

4. Install dependencies:

```powershell
pip install -r requirements.txt
```

## Database Setup
Run migrations:

```powershell
python manage.py makemigrations
python manage.py migrate
```

## Run the App
Start the development server:

```powershell
python manage.py runserver
```

Open in browser:
- http://127.0.0.1:8000/

## Screenshots

### App Preview 1
![Trip Canvas app preview 1](Screenshots/Screenshot%202026-04-06%20213224.png)

### App Preview 2
![Trip Canvas app preview 2](Screenshots/Screenshot%202026-04-06%20213241.png)

### App Preview 3
![Trip Canvas app preview 3](Screenshots/Screenshot%202026-04-06%20213250.png)

### App Preview 4
![Trip Canvas app preview 4](Screenshots/Screenshot%202026-04-06%20213301.png)

### App Preview 5
![Trip Canvas app preview 5](Screenshots/Screenshot%202026-04-06%20213324.png)

### App Preview 6
![Trip Canvas app preview 6](Screenshots/Screenshot%202026-04-06%20213335.png)

### App Preview 7
![Trip Canvas app preview 7](Screenshots/Screenshot%202026-04-06%20213358.png)

## Authentication Routes
- Signup: `/signup/`
- Login: `/accounts/login/`
- Logout: `/accounts/logout/`

## Main Routes
- Trip list: `/`
- Create trip: `/trips/new/`
- Trip detail: `/trips/<trip_id>/`
- AI help: `/trips/<trip_id>/ai-help/`
- Toggle checklist item done: `/checklist/<item_id>/toggle/`

## Map Support
- Trip creation includes a destination search helper that can populate latitude and longitude from OpenStreetMap search results.
- Trip detail pages show a Leaflet map with the destination marker and any saved places.
- Saved places can be added directly from the trip page and used to draw a simple route line.

## Weather Intelligence
- Trip detail pages fetch current weather and a 5-day forecast using destination coordinates.
- Weather warnings are shown when high-risk conditions are detected.
- The planner suggests a better sightseeing day based on forecast quality.
- If coordinates are missing or the weather API is unavailable, the UI falls back gracefully.

## Live AI Setup
- Recommended: use a local `.env` file to avoid terminal environment issues.
- This repo includes `.env.example` and a local `.env` scaffold.
- Put your key in `.env` as `OPENAI_API_KEY=your_real_key`.
- Optional: set `OPENAI_MODEL` to change the model name. The app defaults to `gpt-4o-mini`.
- Optional: set `OPENAI_API_URL` if you need a custom-compatible endpoint.
- Optional: set `OPENAI_TIMEOUT_SECONDS` (recommended 90-180 for local models like Ollama/DeepSeek R1).
- Optional: set `OPENAI_MAX_TOKENS` to constrain response size and reduce latency.
- If the API key is missing or the model call fails, the app automatically uses the rule-based fallback planner.

Quick start:

```powershell
# 1) Edit .env and paste your key
OPENAI_API_KEY=your_real_key_here

# 2) Start server normally (the app auto-loads .env)
python manage.py runserver
```

## Admin
Create a superuser:

```powershell
python manage.py createsuperuser
```

Or use the project helper command:

```powershell
python manage.py create_default_superuser
```

Useful options:

```powershell
# Fully non-interactive
python manage.py create_default_superuser --username admin --email admin@example.com --password "ChangeMe123!" --no-input

# Update existing admin credentials if it already exists
python manage.py create_default_superuser --username admin --email admin@example.com --password "ChangeMe123!" --no-input --update-existing
```

Admin site:
- http://127.0.0.1:8000/admin/

## Notes
- Data is user-scoped: users only see and manage their own trips and related items.
- Weather-aware suggestions are currently rule-based (season + interests) and can be upgraded later to use a live weather API.
