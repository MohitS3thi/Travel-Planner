from django.contrib import admin
from .models import ChecklistItem, ItineraryItem, Place, Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
	list_display = ('destination', 'owner', 'start_date', 'end_date', 'budget', 'status')
	list_filter = ('status',)
	search_fields = ('destination', 'owner__username')


@admin.register(ItineraryItem)
class ItineraryItemAdmin(admin.ModelAdmin):
	list_display = ('title', 'trip', 'date', 'estimated_cost')
	list_filter = ('date',)


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
	list_display = ('item_name', 'trip', 'category', 'is_done')
	list_filter = ('category', 'is_done')


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
	list_display = (
		'name',
		'trip',
		'place_type',
		'visit_date',
		'return_date',
		'is_one_day_visit',
		'latitude',
		'longitude',
		'created_at',
	)
	list_filter = ('place_type',)
	search_fields = ('name', 'address', 'trip__destination')
