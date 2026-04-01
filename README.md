# Travel Planner (Django)

A basic travel-planner web app built with Django where users can:
- Sign up, log in, and log out
- Create trips with destination, dates, budget, and interests
- View trip details
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

## Admin
Create a superuser:

```powershell
python manage.py createsuperuser
```

Admin site:
- http://127.0.0.1:8000/admin/

## Notes
- Data is user-scoped: users only see and manage their own trips and related items.
- Weather-aware suggestions are currently rule-based (season + interests) and can be upgraded later to use a live weather API.
