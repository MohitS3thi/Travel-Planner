from django.db import models
from django.contrib.auth.models import User


class Trip(models.Model):
	STATUS_PLANNED = 'planned'
	STATUS_COMPLETED = 'completed'
	STATUS_CANCELLED = 'cancelled'
	STATUS_CHOICES = [
		(STATUS_PLANNED, 'Planned'),
		(STATUS_COMPLETED, 'Completed'),
		(STATUS_CANCELLED, 'Cancelled'),
	]

	owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trips')
	destination = models.CharField(max_length=120)
	destination_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
	destination_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
	start_date = models.DateField()
	end_date = models.DateField()
	budget = models.DecimalField(max_digits=10, decimal_places=2)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
	interests = models.TextField(blank=True, help_text='Example: food, museums, hiking, nightlife')
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-start_date', '-created_at']
		constraints = [
			models.CheckConstraint(
				check=models.Q(end_date__gte=models.F('start_date')),
				name='trip_end_date_on_or_after_start_date',
			),
		]

	def __str__(self):
		return f'{self.destination} ({self.start_date} - {self.end_date})'


class Place(models.Model):
	PLACE_TYPES = [
		('attraction', 'Attraction'),
		('restaurant', 'Restaurant'),
		('hotel', 'Hotel'),
		('activity', 'Activity'),
		('viewpoint', 'Viewpoint'),
		('other', 'Other'),
	]

	trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='places')
	name = models.CharField(max_length=160)
	place_type = models.CharField(max_length=20, choices=PLACE_TYPES, default='other')
	address = models.CharField(max_length=255, blank=True)
	latitude = models.DecimalField(max_digits=9, decimal_places=6)
	longitude = models.DecimalField(max_digits=9, decimal_places=6)
	visit_date = models.DateField(null=True, blank=True)
	return_date = models.DateField(null=True, blank=True)
	is_one_day_visit = models.BooleanField(default=False)
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at']

	def __str__(self):
		return f'{self.name} ({self.trip.destination})'


class ItineraryItem(models.Model):
	trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='itinerary_items')
	date = models.DateField()
	start_time = models.TimeField(null=True, blank=True)
	end_time = models.TimeField(null=True, blank=True)
	title = models.CharField(max_length=150)
	notes = models.TextField(blank=True)
	estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['date', 'start_time', 'created_at']

	def __str__(self):
		return f'{self.title} on {self.date}'


class TripRoute(models.Model):
	trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='routes')
	name = models.CharField(max_length=180)
	start_key = models.CharField(max_length=80)
	start_name = models.CharField(max_length=160)
	start_lat = models.DecimalField(max_digits=9, decimal_places=6)
	start_lng = models.DecimalField(max_digits=9, decimal_places=6)
	end_key = models.CharField(max_length=80)
	end_name = models.CharField(max_length=160)
	end_lat = models.DecimalField(max_digits=9, decimal_places=6)
	end_lng = models.DecimalField(max_digits=9, decimal_places=6)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.name} ({self.trip.destination})'


class ChecklistItem(models.Model):
	CATEGORY_CHOICES = [
		('hotel', 'Hotel'),
		('transport', 'Train/Transport Tickets'),
		('visa', 'Visa/Documents'),
		('packing', 'Packing'),
		('other', 'Other'),
	]

	trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='checklist_items')
	category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
	item_name = models.CharField(max_length=150)
	is_done = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['is_done', 'category', 'created_at']

	def __str__(self):
		return self.item_name

