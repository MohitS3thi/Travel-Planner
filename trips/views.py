import json
import os
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from .ai_planner import generate_personalized_itinerary
from .forms import AIItineraryHelpForm, ChecklistItemForm, ItineraryItemForm, PlaceForm, SignUpForm, TripForm, TripRouteForm
from .models import ChecklistItem, ItineraryItem, Place, Trip, TripRoute
from .utils import generate_weather_aware_suggestions
from .weather import get_weather_for_coordinates, get_weather_for_place_date


RECOMMENDED_SEARCHES = [
	{'query': 'weather', 'label': 'Weather forecast'},
	{'query': 'itinerary', 'label': 'Itinerary planning'},
	{'query': 'map', 'label': 'Map and saved places'},
	{'query': 'route', 'label': 'Route planner'},
	{'query': 'checklist', 'label': 'Checklist prep'},
	{'query': 'ai help', 'label': 'AI trip assistant'},
]

FEATURE_KEYWORDS = {
	'Weather': ['weather', 'forecast', 'rain', 'temperature', 'climate'],
	'Itinerary & Budget': ['itinerary', 'budget', 'activity', 'activities', 'plan'],
	'Map & Places': ['map', 'place', 'places', 'location', 'locations'],
	'Route Planner': ['route', 'routes', 'path', 'directions'],
	'Checklist': ['checklist', 'packing', 'prep', 'to-do', 'todo'],
	'AI Help': ['ai', 'assistant', 'ai help'],
}


def _matched_feature_labels(search_query):
	if not search_query:
		return []

	query_text = search_query.lower()
	matched = []
	for feature_label, keywords in FEATURE_KEYWORDS.items():
		if any(keyword in query_text for keyword in keywords):
			matched.append(feature_label)
	return matched


def _feature_intent_label(search_query):
	"""Return a feature label only when query is an explicit feature intent."""
	if not search_query:
		return None

	query_text = search_query.strip().lower()
	for feature_label, keywords in FEATURE_KEYWORDS.items():
		if any(query_text == keyword for keyword in keywords):
			return feature_label
	return None


def _feature_redirect_url(feature_label, trip_id):
	if feature_label == 'Weather':
		return reverse('trip_weather', kwargs={'trip_id': trip_id})
	if feature_label == 'Itinerary & Budget':
		return reverse('trip_itinerary', kwargs={'trip_id': trip_id})
	if feature_label == 'Map & Places':
		return f"{reverse('trip_itinerary', kwargs={'trip_id': trip_id})}#itinerary-places-section"
	if feature_label == 'Route Planner':
		return f"{reverse('trip_detail', kwargs={'trip_id': trip_id})}#trip-route-section"
	if feature_label == 'Checklist':
		return f"{reverse('trip_detail', kwargs={'trip_id': trip_id})}#trip-checklist-section"
	if feature_label == 'AI Help':
		return reverse('ai_help', kwargs={'trip_id': trip_id})
	return None


def _feature_action_text(feature_label):
	if feature_label == 'Weather':
		return 'Open weather insights'
	if feature_label == 'Itinerary & Budget':
		return 'Open itinerary and budget'
	if feature_label == 'Map & Places':
		return 'Open map and places'
	if feature_label == 'Route Planner':
		return 'Open route planner'
	if feature_label == 'Checklist':
		return 'Open checklist'
	if feature_label == 'AI Help':
		return 'Open AI Help'
	return 'Open feature'


@method_decorator(never_cache, name='dispatch')
@method_decorator(ensure_csrf_cookie, name='dispatch')
class CustomLoginView(LoginView):
	template_name = 'registration/login.html'
	redirect_authenticated_user = True


def _build_trip_point_lookup(trip):
	lookup = {}

	if trip.destination_lat is not None and trip.destination_lng is not None:
		lookup['destination'] = {
			'name': trip.destination,
			'lat': float(trip.destination_lat),
			'lng': float(trip.destination_lng),
		}

	for place in trip.places.all():
		lookup[f'place-{place.id}'] = {
			'name': place.name,
			'lat': float(place.latitude),
			'lng': float(place.longitude),
		}

	return lookup


def _route_color_for_id(route_id):
	palette = ['#2ca57e', '#f2be63', '#4ea1ff', '#d96b9d', '#7fc8a9', '#ff8a5c', '#8d7cff']
	return palette[route_id % len(palette)]


def _trip_default_weather_summary(weather_payload):
	if not weather_payload:
		return ''

	current = weather_payload.get('current') or {}
	trip_forecast = weather_payload.get('trip_forecast') or []
	parts = []

	if current.get('weather_label'):
		parts.append(f"Current: {current['weather_label']}")
	if current.get('temperature') is not None:
		parts.append(f"{current['temperature']} deg C")

	if trip_forecast:
		driest = min(trip_forecast, key=lambda day: day.get('precipitation_probability') or 0)
		wettest = max(trip_forecast, key=lambda day: day.get('precipitation_probability') or 0)
		parts.append(
			f"Driest day around {driest.get('date')} ({driest.get('precipitation_probability', 0)}% rain chance)"
		)
		parts.append(
			f"Highest rain chance around {wettest.get('date')} ({wettest.get('precipitation_probability', 0)}%)"
		)

	if weather_payload.get('warning'):
		parts.append(weather_payload['warning'].get('message', ''))

	return '. '.join(part for part in parts if part)


def _serialize_ai_plan(value):
	if isinstance(value, dict):
		return {key: _serialize_ai_plan(inner_value) for key, inner_value in value.items()}
	if isinstance(value, list):
		return [_serialize_ai_plan(item) for item in value]
	if isinstance(value, Decimal):
		return str(value)
	return value


def _store_ai_plan_in_session(request, plan):
	request.session['last_ai_plan'] = json.dumps(_serialize_ai_plan(plan), ensure_ascii=True)
	request.session.modified = True


def _load_ai_plan_from_session(request):
	plan_text = request.session.get('last_ai_plan')
	if not plan_text:
		return None
	try:
		return json.loads(plan_text)
	except json.JSONDecodeError:
		return None


def _save_ai_plan_to_itinerary(trip, plan):
	created_count = 0
	day_items = plan.get('day_wise_itinerary') or []

	if not day_items:
		return 0

	start_date = trip.start_date
	if start_date is None:
		return 0

	TripItineraryPrefix = f'AI Plan - {trip.destination} - Day '
	trip.itinerary_items.filter(title__startswith=TripItineraryPrefix).delete()

	for day in day_items:
		day_number = int(day.get('day_number') or created_count + 1)
		trip_date_text = (day.get('trip_date') or '').strip() if isinstance(day.get('trip_date'), str) else ''
		if trip_date_text:
			try:
				day_date = datetime.strptime(trip_date_text, '%Y-%m-%d').date()
			except ValueError:
				day_date = start_date + timedelta(days=max(0, day_number - 1))
		else:
			day_date = start_date + timedelta(days=max(0, day_number - 1))
		budget = day.get('budget') or {}
		estimated_cost = Decimal(str(budget.get('total', '0') or '0'))
		morning = (day.get('morning') or '').strip()
		afternoon = (day.get('afternoon') or '').strip()
		evening = (day.get('evening') or '').strip()
		window_parts = [
			f"Morning: {morning}" if morning else 'Morning: not specified',
			f"Afternoon: {afternoon}" if afternoon else 'Afternoon: not specified',
			f"Evening: {evening}" if evening else 'Evening: not specified',
			f"Budget: ₹{estimated_cost}",
		]
		ItineraryItem.objects.create(
			trip=trip,
			date=day_date,
			title=f'AI Plan - {trip.destination} - Day {day_number}',
			notes=' | '.join(window_parts),
			estimated_cost=estimated_cost,
		)
		created_count += 1

	return created_count


def home_view(request):
	if request.user.is_authenticated:
		return redirect('trip_list')
	return render(request, 'home.html')


def signup_view(request):
	if request.user.is_authenticated:
		return redirect('trip_list')

	form = SignUpForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.save()
		login(request, user)
		return redirect('trip_list')
	return render(request, 'registration/signup.html', {'form': form})


@login_required
def trip_list(request):
	trips = Trip.objects.filter(owner=request.user)
	search_query = (request.GET.get('q') or '').strip()
	matched_feature_labels = _matched_feature_labels(search_query)
	feature_intent_label = _feature_intent_label(search_query)
	selected_status = request.GET.get('status', 'all').strip().lower()
	allowed_statuses = {choice[0] for choice in Trip.STATUS_CHOICES}

	# For explicit feature-intent searches (e.g. "weather"), prompt for planned trip selection.
	if feature_intent_label:
		planned_trips = trips.filter(status=Trip.STATUS_PLANNED).order_by('-start_date', '-id')

		if not planned_trips.exists():
			return render(
				request,
				'trips/feature_trip_picker.html',
				{
					'feature_label': feature_intent_label,
					'feature_query': search_query,
					'feature_action_text': _feature_action_text(feature_intent_label),
					'trip_choices': [],
					'has_any_trips': trips.exists(),
				},
			)

		trip_choices = []
		for trip in planned_trips:
			feature_url = _feature_redirect_url(feature_intent_label, trip.id)
			if feature_url:
				trip_choices.append({'trip': trip, 'feature_url': feature_url})

		return render(
			request,
			'trips/feature_trip_picker.html',
			{
				'feature_label': feature_intent_label,
				'feature_query': search_query,
				'feature_action_text': _feature_action_text(feature_intent_label),
				'trip_choices': trip_choices,
				'has_any_trips': trips.exists(),
			},
		)

	if search_query:
		text_matches = trips.filter(
			Q(destination__icontains=search_query)
			| Q(interests__icontains=search_query)
			| Q(places__name__icontains=search_query)
			| Q(itinerary_items__title__icontains=search_query)
			| Q(itinerary_items__notes__icontains=search_query)
		).distinct()

		# Feature search terms (e.g. "weather", "map", "ai help") should surface trips too.
		if matched_feature_labels:
			trips = trips.distinct()
		else:
			trips = text_matches

	if selected_status in allowed_statuses:
		trips = trips.filter(status=selected_status)
	else:
		selected_status = 'all'

	return render(
		request,
		'trips/trip_list.html',
		{
			'trips': trips,
			'selected_status': selected_status,
			'search_query': search_query,
			'matched_feature_labels': matched_feature_labels,
			'recommended_searches': RECOMMENDED_SEARCHES,
		},
	)


@login_required
def trip_create(request):
	form = TripForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		trip = form.save(commit=False)
		trip.owner = request.user
		trip.save()
		return redirect('trip_detail', trip_id=trip.id)
	return render(request, 'trips/trip_form.html', {'form': form})


@login_required
def trip_edit(request, trip_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	form = TripForm(request.POST or None, instance=trip)

	if request.method == 'POST' and form.is_valid():
		form.save()
		return redirect('trip_detail', trip_id=trip.id)

	return render(
		request,
		'trips/trip_form.html',
		{
			'form': form,
			'is_edit_mode': True,
			'trip': trip,
		},
	)


@login_required
def trip_detail(request, trip_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	itinerary_form = ItineraryItemForm(request.POST or None, prefix='itinerary', trip=trip)
	checklist_form = ChecklistItemForm(request.POST or None, prefix='checklist')
	point_lookup = _build_trip_point_lookup(trip)
	point_choices = [(key, point['name']) for key, point in point_lookup.items()]
	route_form = TripRouteForm(request.POST or None, point_choices=point_choices)

	if request.method == 'POST':
		if 'update_trip_status' in request.POST:
			new_status = request.POST.get('trip_status', '').strip()
			allowed_statuses = {choice[0] for choice in Trip.STATUS_CHOICES}
			if new_status in allowed_statuses and trip.status != new_status:
				trip.status = new_status
				trip.save(update_fields=['status'])
			return redirect('trip_detail', trip_id=trip.id)

		if 'delete_trip' in request.POST:
			trip.delete()
			return redirect('trip_list')

		if 'add_itinerary' in request.POST and itinerary_form.is_valid():
			itinerary_item = itinerary_form.save(commit=False)
			itinerary_item.trip = trip
			itinerary_item.save()
			return redirect('trip_detail', trip_id=trip.id)

		if 'add_checklist' in request.POST and checklist_form.is_valid():
			checklist_item = checklist_form.save(commit=False)
			checklist_item.trip = trip
			checklist_item.save()
			return redirect('trip_detail', trip_id=trip.id)

		if 'create_route' in request.POST and route_form.is_valid():
			start_key = route_form.cleaned_data['start_key']
			end_key = route_form.cleaned_data['end_key']
			start_point = point_lookup.get(start_key)
			end_point = point_lookup.get(end_key)

			if start_point and end_point:
				route_name = (route_form.cleaned_data.get('route_name') or '').strip() or f"{start_point['name']} to {end_point['name']}"
				TripRoute.objects.create(
					trip=trip,
					name=route_name,
					start_key=start_key,
					start_name=start_point['name'],
					start_lat=Decimal(str(start_point['lat'])),
					start_lng=Decimal(str(start_point['lng'])),
					end_key=end_key,
					end_name=end_point['name'],
					end_lat=Decimal(str(end_point['lat'])),
					end_lng=Decimal(str(end_point['lng'])),
				)
				return redirect('trip_detail', trip_id=trip.id)

	weather = get_weather_for_coordinates(
		trip.destination_lat,
		trip.destination_lng,
		forecast_days=5,
		trip_start_date=trip.start_date,
	)
	suggestions = generate_weather_aware_suggestions(trip)
	if weather and weather.get('recommendation'):
		suggestions['tips'].insert(0, weather['recommendation'])
	map_points = []
	if trip.destination_lat is not None and trip.destination_lng is not None:
		map_points.append({
			'key': 'destination',
			'name': trip.destination,
			'type': 'destination',
			'lat': float(trip.destination_lat),
			'lng': float(trip.destination_lng),
			'address': trip.destination,
		})

	for place in trip.places.all():
		map_points.append({
			'key': f'place-{place.id}',
			'name': place.name,
			'type': place.place_type,
			'lat': float(place.latitude),
			'lng': float(place.longitude),
			'address': place.address,
			'notes': place.notes,
		})

	route_rows = []
	routes_data = []
	for route in trip.routes.all():
		color = _route_color_for_id(route.id)
		route_rows.append({'route': route, 'color': color})
		routes_data.append({
			'id': route.id,
			'name': route.name,
			'color': color,
			'start_name': route.start_name,
			'end_name': route.end_name,
			'start_lat': float(route.start_lat),
			'start_lng': float(route.start_lng),
			'end_lat': float(route.end_lat),
			'end_lng': float(route.end_lng),
		})
	return render(
		request,
		'trips/trip_detail.html',
		{
			'trip': trip,
			'itinerary_form': itinerary_form,
			'checklist_form': checklist_form,
			'route_form': route_form,
			'suggestions': suggestions,
			'weather': weather,
			'map_points': map_points,
			'route_rows': route_rows,
			'routes_data': routes_data,
		},
	)


@login_required
def edit_route(request, trip_id, route_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	route = get_object_or_404(TripRoute, id=route_id, trip=trip)

	point_lookup = _build_trip_point_lookup(trip)
	point_choices = [(key, point['name']) for key, point in point_lookup.items()]

	if request.method == 'POST':
		form = TripRouteForm(request.POST, point_choices=point_choices)
		if form.is_valid():
			start_key = form.cleaned_data['start_key']
			end_key = form.cleaned_data['end_key']
			start_point = point_lookup.get(start_key)
			end_point = point_lookup.get(end_key)

			if start_point and end_point:
				route.name = (form.cleaned_data.get('route_name') or '').strip() or f"{start_point['name']} to {end_point['name']}"
				route.start_key = start_key
				route.start_name = start_point['name']
				route.start_lat = Decimal(str(start_point['lat']))
				route.start_lng = Decimal(str(start_point['lng']))
				route.end_key = end_key
				route.end_name = end_point['name']
				route.end_lat = Decimal(str(end_point['lat']))
				route.end_lng = Decimal(str(end_point['lng']))
				route.save()
				return redirect('trip_detail', trip_id=trip.id)
	else:
		form = TripRouteForm(
			point_choices=point_choices,
			initial={
				'route_name': route.name,
				'start_key': route.start_key,
				'end_key': route.end_key,
			},
		)

	return render(
		request,
		'trips/edit_route.html',
		{
			'trip': trip,
			'route': route,
			'form': form,
		},
	)


@login_required
def delete_route(request, trip_id, route_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	route = get_object_or_404(TripRoute, id=route_id, trip=trip)

	if request.method == 'POST':
		route.delete()
		return redirect('trip_detail', trip_id=trip.id)

	return render(
		request,
		'trips/delete_route.html',
		{
			'trip': trip,
			'route': route,
		},
	)


@login_required
def trip_weather(request, trip_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	weather = get_weather_for_coordinates(
		trip.destination_lat,
		trip.destination_lng,
		forecast_days=5,
		trip_start_date=trip.start_date,
	)
	suggestions = generate_weather_aware_suggestions(trip)
	if weather and weather.get('recommendation'):
		suggestions['tips'].insert(0, weather['recommendation'])

	return render(
		request,
		'trips/trip_weather.html',
		{
			'trip': trip,
			'weather': weather,
			'suggestions': suggestions,
		},
	)


@login_required
def ai_help(request, trip_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	generated_plan = None
	ai_source = None
	ai_model = None

	if request.method == 'POST' and 'save_ai_plan' in request.POST:
		stored_plan = _load_ai_plan_from_session(request)
		if not stored_plan:
			messages.error(request, 'Generate an AI itinerary first, then save it to the itinerary tab.')
			return redirect('ai_help', trip_id=trip.id)

		created_count = _save_ai_plan_to_itinerary(trip, stored_plan)
		if created_count:
			request.session.pop('last_ai_plan', None)
			request.session.modified = True
			messages.success(
				request,
				f"Added {created_count} AI day plan{'s' if created_count != 1 else ''} to the itinerary tab.",
			)
			return redirect('trip_itinerary', trip_id=trip.id)

		messages.error(request, 'No AI itinerary days were available to save.')
		return redirect('ai_help', trip_id=trip.id)

	weather = get_weather_for_coordinates(
		trip.destination_lat,
		trip.destination_lng,
		forecast_days=5,
		trip_start_date=trip.start_date,
	)

	default_weather_summary = _trip_default_weather_summary(weather)

	default_style = 'custom'
	interests_text = (trip.interests or '').lower()
	for style_option in ('solo', 'family', 'adventure', 'food'):
		if style_option in interests_text:
			default_style = style_option
			break

	initial_data = {
		'destination': trip.destination,
		'generate_from_date': trip.start_date,
		'generate_to_date': trip.end_date,
		'budget': trip.budget,
		'travel_style': default_style,
		'custom_travel_style': '' if default_style != 'custom' else (trip.interests or ''),
		'use_auto_weather': True,
		'weather_summary': default_weather_summary,
		'preferred_start_time': '08:00',
		'preferred_end_time': '21:00',
	}

	form = AIItineraryHelpForm(request.POST or None, initial=initial_data, trip=trip)
	generated_plan = None

	if request.method == 'POST' and form.is_valid():
		cleaned = form.cleaned_data
		selected_dates = []
		for date_text in (cleaned.get('selected_trip_dates') or []):
			try:
				selected_dates.append(datetime.strptime(date_text, '%Y-%m-%d').date())
			except ValueError:
				continue

		existing_items_for_selected_dates = trip.itinerary_items.filter(date__in=selected_dates) if selected_dates else trip.itinerary_items.none()
		total_trip_days = max(1, (trip.end_date - trip.start_date).days + 1)
		weather_text = default_weather_summary if cleaned.get('use_auto_weather') else (cleaned.get('weather_summary') or '')
		generated_plan = generate_personalized_itinerary(
			destination=cleaned['destination'],
			selected_trip_dates=cleaned['selected_trip_dates'],
			budget=cleaned['budget'],
			total_trip_days=total_trip_days,
			travel_style=cleaned['travel_style_text'],
			weather_summary=weather_text,
			preferred_start_time=cleaned['preferred_start_time'],
			preferred_end_time=cleaned['preferred_end_time'],
			saved_places=trip.places.all(),
			existing_itinerary_items=existing_items_for_selected_dates,
		)
		_store_ai_plan_in_session(request, generated_plan)

	generated_source = None
	generated_model = None
	fallback_reason = None
	if generated_plan:
		generated_source = generated_plan.get('source') or generated_plan.get('summary', {}).get('source')
		generated_model = generated_plan.get('summary', {}).get('model_name')
		fallback_reason = generated_plan.get('summary', {}).get('fallback_reason')

	has_openai_key = bool((os.getenv('OPENAI_API_KEY') or '').strip())

	return render(
		request,
		'trips/ai_help.html',
		{
			'trip': trip,
			'form': form,
			'weather': weather,
			'generated_plan': generated_plan,
			'ai_source': generated_source,
			'ai_model': generated_model,
			'ai_fallback_reason': fallback_reason,
			'has_openai_key': has_openai_key,
		},
	)


@login_required
def place_weather(request, trip_id, place_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	place = get_object_or_404(Place, id=place_id, trip=trip)

	default_date = place.visit_date or trip.start_date
	selected_date_text = request.GET.get('date') or (default_date.isoformat() if default_date else '')
	selected_date = None
	if selected_date_text:
		try:
			selected_date = datetime.strptime(selected_date_text, '%Y-%m-%d').date()
		except ValueError:
			selected_date = None

	trip_date_error = None
	if selected_date and (selected_date < trip.start_date or selected_date > trip.end_date):
		trip_date_error = 'Selected date must be within your trip dates.'
		place_weather_data = {
			'selected_date': selected_date_text,
			'forecast_day': None,
			'notice': trip_date_error,
			'available_from': None,
			'available_in_days': 0,
		}
	else:
		place_weather_data = get_weather_for_place_date(place.latitude, place.longitude, selected_date_text)

	return render(
		request,
		'trips/place_weather.html',
		{
			'trip': trip,
			'place': place,
			'place_weather': place_weather_data,
			'selected_date_text': selected_date_text,
		},
	)


@login_required
def trip_itinerary(request, trip_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	itinerary_items = trip.itinerary_items.all().order_by('date', 'start_time', 'created_at')
	place_form = PlaceForm(request.POST or None, prefix='place', trip=trip)
	
	if request.method == 'POST' and 'add_place' in request.POST:
		if place_form.is_valid():
			place = place_form.save(commit=False)
			place.trip = trip
			place.save()

			if place_form.cleaned_data.get('add_to_itinerary'):
				ItineraryItem.objects.create(
					trip=trip,
					date=place_form.cleaned_data['visit_date'],
					start_time=place_form.cleaned_data.get('itinerary_start_time'),
					end_time=place_form.cleaned_data.get('itinerary_end_time'),
					title=place_form.cleaned_data.get('itinerary_title') or f'Visit {place.name}',
					notes=place.notes,
					estimated_cost=place_form.cleaned_data.get('itinerary_estimated_cost') or 0,
				)
			messages.success(request, 'Place saved successfully.')
			return redirect('trip_itinerary', trip_id=trip.id)

		messages.error(request, 'Could not save place. Please fix the highlighted fields and try again.')
	
	# Calculate budget summary
	total_spent = sum(item.estimated_cost for item in itinerary_items)
	remaining_budget = trip.budget - total_spent
	over_budget_amount = abs(remaining_budget) if remaining_budget < 0 else 0
	
	# Add budget percentage calculation for each item
	budget_items = []
	for item in itinerary_items:
		percentage = (item.estimated_cost / trip.budget * 100) if trip.budget > 0 else 0
		capped_percentage = min(percentage, 100)  # Cap at 100 for visualization
		budget_items.append({
			'item': item,
			'percentage': percentage,
			'capped_percentage': capped_percentage,
		})
	
	# Build map points data
	map_points = []
	if trip.destination_lat is not None and trip.destination_lng is not None:
		map_points.append({
			'key': 'destination',
			'name': trip.destination,
			'type': 'destination',
			'lat': float(trip.destination_lat),
			'lng': float(trip.destination_lng),
			'address': trip.destination,
		})

	for place in trip.places.all():
		map_points.append({
			'key': f'place-{place.id}',
			'name': place.name,
			'type': place.place_type,
			'lat': float(place.latitude),
			'lng': float(place.longitude),
			'address': place.address,
			'notes': place.notes,
		})
	
	return render(
		request,
		'trips/trip_itinerary.html',
		{
			'trip': trip,
			'place_form': place_form,
			'budget_items': budget_items,
			'total_spent': total_spent,
			'remaining_budget': remaining_budget,
			'over_budget_amount': over_budget_amount,
			'budget_percentage': (total_spent / trip.budget * 100) if trip.budget > 0 else 0,
			'map_points': map_points,
		},
	)


@login_required
def edit_place(request, trip_id, place_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	place = get_object_or_404(Place, id=place_id, trip=trip)
	
	if request.method == 'POST':
		place_form = PlaceForm(request.POST, instance=place, prefix='place', trip=trip)
		if place_form.is_valid():
			place = place_form.save(commit=False)
			place.trip = trip
			place.save()
			
			# Handle itinerary updates if place is being added to itinerary
			if place_form.cleaned_data.get('add_to_itinerary'):
				visit_date = place_form.cleaned_data.get('visit_date')
				if visit_date:
					# Remove existing itinerary item for this place if it exists
					ItineraryItem.objects.filter(
						trip=trip,
						title__contains=place.name
					).delete()
					# Create new itinerary item
					ItineraryItem.objects.create(
						trip=trip,
						date=visit_date,
						start_time=place_form.cleaned_data.get('itinerary_start_time'),
						end_time=place_form.cleaned_data.get('itinerary_end_time'),
						title=place_form.cleaned_data.get('itinerary_title') or f'Visit {place.name}',
						notes=place.notes,
						estimated_cost=place_form.cleaned_data.get('itinerary_estimated_cost') or 0,
					)
			return redirect('trip_itinerary', trip_id=trip.id)
	else:
		place_form = PlaceForm(instance=place, prefix='place', trip=trip)
	
	return render(
		request,
		'trips/edit_place.html',
		{
			'trip': trip,
			'place': place,
			'place_form': place_form,
		},
	)


@login_required
def delete_place(request, trip_id, place_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	place = get_object_or_404(Place, id=place_id, trip=trip)
	
	if request.method == 'POST':
		# Also delete associated itinerary items
		ItineraryItem.objects.filter(trip=trip, title__contains=place.name).delete()
		place.delete()
		return redirect('trip_itinerary', trip_id=trip.id)
	
	return render(
		request,
		'trips/delete_place.html',
		{
			'trip': trip,
			'place': place,
		},
	)


@login_required
def edit_itinerary_item(request, trip_id, item_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	item = get_object_or_404(ItineraryItem, id=item_id, trip=trip)
	
	if request.method == 'POST':
		form = ItineraryItemForm(request.POST, instance=item, prefix='itinerary', trip=trip)
		if form.is_valid():
			form.save()
			return redirect('trip_itinerary', trip_id=trip.id)
	else:
		form = ItineraryItemForm(instance=item, prefix='itinerary', trip=trip)
	
	return render(
		request,
		'trips/edit_itinerary_item.html',
		{
			'trip': trip,
			'item': item,
			'form': form,
		},
	)


@login_required
def delete_itinerary_item(request, trip_id, item_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	item = get_object_or_404(ItineraryItem, id=item_id, trip=trip)
	
	if request.method == 'POST':
		item.delete()
		return redirect('trip_itinerary', trip_id=trip.id)
	
	return render(
		request,
		'trips/delete_itinerary_item.html',
		{
			'trip': trip,
			'item': item,
		},
	)


@login_required
def toggle_checklist_item(request, item_id):
	item = get_object_or_404(ChecklistItem, id=item_id, trip__owner=request.user)
	item.is_done = not item.is_done
	item.save(update_fields=['is_done'])
	return redirect('trip_detail', trip_id=item.trip.id)
