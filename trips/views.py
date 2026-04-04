from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ChecklistItemForm, ItineraryItemForm, PlaceForm, SignUpForm, TripForm
from .models import ChecklistItem, Trip
from .utils import generate_weather_aware_suggestions


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
	selected_status = request.GET.get('status', 'all').strip().lower()
	allowed_statuses = {choice[0] for choice in Trip.STATUS_CHOICES}

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
def trip_detail(request, trip_id):
	trip = get_object_or_404(Trip, id=trip_id, owner=request.user)
	itinerary_form = ItineraryItemForm(request.POST or None, prefix='itinerary')
	checklist_form = ChecklistItemForm(request.POST or None, prefix='checklist')
	place_form = PlaceForm(request.POST or None, prefix='place')

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

		if 'add_place' in request.POST and place_form.is_valid():
			place = place_form.save(commit=False)
			place.trip = trip
			place.save()
			return redirect('trip_detail', trip_id=trip.id)

	suggestions = generate_weather_aware_suggestions(trip)
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
		'trips/trip_detail.html',
		{
			'trip': trip,
			'itinerary_form': itinerary_form,
			'checklist_form': checklist_form,
			'place_form': place_form,
			'suggestions': suggestions,
			'map_points': map_points,
		},
	)


@login_required
def toggle_checklist_item(request, item_id):
	item = get_object_or_404(ChecklistItem, id=item_id, trip__owner=request.user)
	item.is_done = not item.is_done
	item.save(update_fields=['is_done'])
	return redirect('trip_detail', trip_id=item.trip.id)
