from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ChecklistItemForm, ItineraryItemForm, SignUpForm, TripForm
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
	return render(request, 'trips/trip_list.html', {'trips': trips})


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

	if request.method == 'POST':
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

	suggestions = generate_weather_aware_suggestions(trip)
	return render(
		request,
		'trips/trip_detail.html',
		{
			'trip': trip,
			'itinerary_form': itinerary_form,
			'checklist_form': checklist_form,
			'suggestions': suggestions,
		},
	)


@login_required
def toggle_checklist_item(request, item_id):
	item = get_object_or_404(ChecklistItem, id=item_id, trip__owner=request.user)
	item.is_done = not item.is_done
	item.save(update_fields=['is_done'])
	return redirect('trip_detail', trip_id=item.trip.id)
