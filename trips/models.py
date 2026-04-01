from django.db import models
from django.contrib.auth.models import User


class Trip(models.Model):
	owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trips')
	destination = models.CharField(max_length=120)
	start_date = models.DateField()
	end_date = models.DateField()
	budget = models.DecimalField(max_digits=10, decimal_places=2)
	interests = models.TextField(help_text='Example: food, museums, hiking, nightlife')
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-start_date', '-created_at']

	def __str__(self):
		return f'{self.destination} ({self.start_date} - {self.end_date})'


class ItineraryItem(models.Model):
	trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='itinerary_items')
	date = models.DateField()
	title = models.CharField(max_length=150)
	notes = models.TextField(blank=True)
	estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['date', 'created_at']

	def __str__(self):
		return f'{self.title} on {self.date}'


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

