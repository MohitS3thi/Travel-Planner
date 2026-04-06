from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from .forms import PlaceForm
from .models import Trip
from .views import _save_ai_plan_to_itinerary
from .weather import build_weather_recommendation
from .weather import _build_specific_date_availability
from .weather import _build_trip_forecast


class WeatherLogicTests(TestCase):
	def test_recommendation_prefers_drier_day(self):
		weather_data = {
			"forecast": [
				{
					"date": "2026-04-05",
					"weather_code": 63,
					"weather_label": "Moderate rain",
					"temp_max": 24,
					"temp_min": 17,
					"precipitation_probability": 80,
					"precipitation_sum": 8.0,
				},
				{
					"date": "2026-04-06",
					"weather_code": 2,
					"weather_label": "Partly cloudy",
					"temp_max": 26,
					"temp_min": 18,
					"precipitation_probability": 20,
					"precipitation_sum": 0.0,
				},
			]
		}

		recommendation = build_weather_recommendation(weather_data)

		self.assertIn("Day 2", recommendation)
		self.assertIn("2026-04-06", recommendation)

	def test_recommendation_handles_poor_weather_window(self):
		weather_data = {
			"forecast": [
				{
					"date": "2026-04-05",
					"weather_code": 63,
					"weather_label": "Moderate rain",
					"temp_max": 19,
					"temp_min": 12,
					"precipitation_probability": 85,
					"precipitation_sum": 10.0,
				},
				{
					"date": "2026-04-06",
					"weather_code": 81,
					"weather_label": "Moderate rain showers",
					"temp_max": 18,
					"temp_min": 11,
					"precipitation_probability": 70,
					"precipitation_sum": 9.0,
				},
			]
		}

		recommendation = build_weather_recommendation(weather_data)

		self.assertIn("indoor activities", recommendation)

	def test_trip_forecast_unavailable_shows_available_from_date(self):
		today = date(2026, 4, 4)
		trip_start = date(2026, 5, 10)

		result = _build_trip_forecast(
			forecast=[],
			trip_start_date=trip_start,
			forecast_days=5,
			today=today,
		)

		self.assertFalse(result["trip_forecast_available"])
		self.assertEqual(result["trip_forecast"], [])
		self.assertEqual(result["trip_forecast_available_from"], "2026-04-25")
		self.assertEqual(result["trip_forecast_available_in_days"], 21)
		self.assertIn("2026-04-25", result["trip_forecast_notice"])

	def test_trip_forecast_starts_from_trip_date(self):
		result = _build_trip_forecast(
			forecast=[
				{"date": "2026-04-04", "weather_label": "Clear sky"},
				{"date": "2026-04-05", "weather_label": "Clear sky"},
				{"date": "2026-04-06", "weather_label": "Partly cloudy"},
				{"date": "2026-04-07", "weather_label": "Overcast"},
			],
			trip_start_date=date(2026, 4, 6),
			forecast_days=3,
			today=date(2026, 4, 4),
		)

		self.assertTrue(result["trip_forecast_available"])
		self.assertEqual([day["date"] for day in result["trip_forecast"]], ["2026-04-06", "2026-04-07"])


class PlaceFormTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='testuser', password='pass12345')
		self.trip = Trip.objects.create(
			owner=self.user,
			destination='Paris',
			start_date=date(2026, 6, 10),
			end_date=date(2026, 6, 20),
			budget='1000.00',
			interests='food, museums',
		)

	def test_one_day_visit_sets_return_date(self):
		form = PlaceForm(
			data={
				'name': 'Louvre Museum',
				'place_type': 'attraction',
				'address': 'Paris',
				'latitude': '48.860611',
				'longitude': '2.337644',
				'visit_date': '2026-06-12',
				'return_date': '',
				'is_one_day_visit': 'on',
				'notes': '',
			},
			trip=self.trip,
		)

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data['return_date'], form.cleaned_data['visit_date'])

	def test_place_dates_must_be_inside_trip_window(self):
		form = PlaceForm(
			data={
				'name': 'Eiffel Tower',
				'place_type': 'attraction',
				'address': 'Paris',
				'latitude': '48.858400',
				'longitude': '2.294500',
				'visit_date': '2026-06-25',
				'return_date': '2026-06-26',
				'notes': '',
			},
			trip=self.trip,
		)

		self.assertFalse(form.is_valid())
		self.assertIn('Visit date must be within the trip dates.', form.non_field_errors())

	def test_place_form_sets_html_date_bounds_from_trip(self):
		form = PlaceForm(trip=self.trip)

		self.assertEqual(form.fields['visit_date'].widget.attrs.get('min'), '2026-06-10')
		self.assertEqual(form.fields['visit_date'].widget.attrs.get('max'), '2026-06-20')
		self.assertEqual(form.fields['return_date'].widget.attrs.get('min'), '2026-06-10')
		self.assertEqual(form.fields['return_date'].widget.attrs.get('max'), '2026-06-20')

	def test_add_to_itinerary_requires_visit_date(self):
		form = PlaceForm(
			data={
				'name': 'Seine Walk',
				'place_type': 'activity',
				'address': 'Paris',
				'latitude': '48.856613',
				'longitude': '2.352222',
				'visit_date': '',
				'return_date': '',
				'add_to_itinerary': 'on',
				'itinerary_title': '',
				'notes': '',
			},
			trip=self.trip,
		)

		self.assertFalse(form.is_valid())
		self.assertIn('Set a visit date when adding this place to itinerary.', form.non_field_errors())

	def test_add_to_itinerary_sets_default_title(self):
		form = PlaceForm(
			data={
				'name': 'Louvre Museum',
				'place_type': 'attraction',
				'address': 'Paris',
				'latitude': '48.860611',
				'longitude': '2.337644',
				'visit_date': '2026-06-14',
				'return_date': '',
				'add_to_itinerary': 'on',
				'itinerary_title': '',
				'notes': '',
			},
			trip=self.trip,
		)

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data['itinerary_title'], 'Visit Louvre Museum')


class PlaceWeatherAvailabilityTests(TestCase):
	def test_specific_date_unavailable_for_far_future(self):
		result = _build_specific_date_availability(date(2026, 5, 10), today=date(2026, 4, 4))

		self.assertFalse(result['can_fetch'])
		self.assertEqual(result['available_from'], '2026-04-25')
		self.assertEqual(result['available_in_days'], 21)

	def test_specific_date_available_inside_horizon(self):
		result = _build_specific_date_availability(date(2026, 4, 10), today=date(2026, 4, 4))

		self.assertTrue(result['can_fetch'])
		self.assertIsNone(result['notice'])


class AiItinerarySaveTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='aiuser', password='pass12345')
		self.trip = Trip.objects.create(
			owner=self.user,
			destination='Tokyo',
			start_date=date(2026, 7, 1),
			end_date=date(2026, 7, 3),
			budget='1500.00',
			interests='food, adventure',
		)

	def test_save_ai_plan_creates_day_items(self):
		plan = {
			'day_wise_itinerary': [
				{
					'day_number': 1,
					'morning': 'Tsukiji market',
					'afternoon': 'Senso-ji and Asakusa walk',
					'evening': 'Dinner in Shibuya',
					'budget': {'total': '300.00'},
				},
				{
					'day_number': 2,
					'morning': 'TeamLab morning slot',
					'afternoon': 'Odaiba waterfront',
					'evening': 'Ramen alley',
					'budget': {'total': '350.00'},
				},
			],
		}

		created_count = _save_ai_plan_to_itinerary(self.trip, plan)

		self.assertEqual(created_count, 2)
		self.assertEqual(self.trip.itinerary_items.count(), 2)
		self.assertEqual(self.trip.itinerary_items.first().title, 'AI Plan - Tokyo - Day 1')
