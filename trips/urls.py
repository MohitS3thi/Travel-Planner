from django.urls import path

from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('trips/', views.trip_list, name='trip_list'),
    path('signup/', views.signup_view, name='signup'),
    path('trips/new/', views.trip_create, name='trip_create'),
    path('trips/<int:trip_id>/edit/', views.trip_edit, name='trip_edit'),
    path('trips/<int:trip_id>/', views.trip_detail, name='trip_detail'),
    path('trips/<int:trip_id>/itinerary/', views.trip_itinerary, name='trip_itinerary'),
    path('trips/<int:trip_id>/itinerary/<int:item_id>/edit/', views.edit_itinerary_item, name='edit_itinerary_item'),
    path('trips/<int:trip_id>/itinerary/<int:item_id>/delete/', views.delete_itinerary_item, name='delete_itinerary_item'),
    path('trips/<int:trip_id>/weather/', views.trip_weather, name='trip_weather'),
    path('trips/<int:trip_id>/places/<int:place_id>/weather/', views.place_weather, name='place_weather'),
    path('trips/<int:trip_id>/places/<int:place_id>/edit/', views.edit_place, name='edit_place'),
    path('trips/<int:trip_id>/places/<int:place_id>/delete/', views.delete_place, name='delete_place'),
    path('trips/<int:trip_id>/routes/<int:route_id>/edit/', views.edit_route, name='edit_route'),
    path('trips/<int:trip_id>/routes/<int:route_id>/delete/', views.delete_route, name='delete_route'),
    path('checklist/<int:item_id>/toggle/', views.toggle_checklist_item, name='toggle_checklist_item'),
]
