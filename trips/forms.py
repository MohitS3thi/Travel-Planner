from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import ChecklistItem, ItineraryItem, Trip


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = ('destination', 'start_date', 'end_date', 'budget', 'interests')
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'interests': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError('End date must be on or after start date.')
        return cleaned_data


class ItineraryItemForm(forms.ModelForm):
    class Meta:
        model = ItineraryItem
        fields = ('date', 'title', 'notes', 'estimated_cost')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ('category', 'item_name')
