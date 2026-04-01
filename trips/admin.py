from django.contrib import admin
from .models import ChecklistItem, ItineraryItem, Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
	list_display = ('destination', 'owner', 'start_date', 'end_date', 'budget')
	search_fields = ('destination', 'owner__username')


@admin.register(ItineraryItem)
class ItineraryItemAdmin(admin.ModelAdmin):
	list_display = ('title', 'trip', 'date', 'estimated_cost')
	list_filter = ('date',)


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
	list_display = ('item_name', 'trip', 'category', 'is_done')
	list_filter = ('category', 'is_done')
