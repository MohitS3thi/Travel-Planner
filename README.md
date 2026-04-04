# Travel Planner (Django)

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

## Authentication Routes
- Signup: `/signup/`
- Login: `/accounts/login/`
- Logout: `/accounts/logout/`

## Main Routes
- Trip list: `/`
- Create trip: `/trips/new/`
- Trip detail: `/trips/<trip_id>/`
- Toggle checklist item done: `/checklist/<item_id>/toggle/`

## Map Support
- Trip creation includes a destination search helper that can populate latitude and longitude from OpenStreetMap search results.
- Trip detail pages show a Leaflet map with the destination marker and any saved places.
- Saved places can be added directly from the trip page and used to draw a simple route line.

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
