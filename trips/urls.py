from django.urls import path

from . import views

urlpatterns = [
    path('', views.trip_list, name='trip_list'),
    path('signup/', views.signup_view, name='signup'),
    path('trips/new/', views.trip_create, name='trip_create'),
    path('trips/<int:trip_id>/', views.trip_detail, name='trip_detail'),
    path('checklist/<int:item_id>/toggle/', views.toggle_checklist_item, name='toggle_checklist_item'),
]
