from django import forms
from datetime import timedelta
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import ChecklistItem, ItineraryItem, Place, Trip


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = ('destination', 'destination_lat', 'destination_lng', 'start_date', 'end_date', 'budget', 'interests')
        widgets = {
            'destination_lat': forms.NumberInput(attrs={'step': 'any'}),
            'destination_lng': forms.NumberInput(attrs={'step': 'any'}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'interests': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['destination_lat'].required = False
        self.fields['destination_lng'].required = False
        self.fields['interests'].required = False
        self.fields['destination_lat'].help_text = 'Optional. Populated automatically by destination search.'
        self.fields['destination_lng'].help_text = 'Optional. Populated automatically by destination search.'
        self.fields['interests'].help_text = 'Optional. You can add or update this later.'

        # Keep end date picker constrained to the selected start date.
        start_date_value = None
        if self.is_bound:
            start_date_value = self.data.get(self.add_prefix('start_date'))
        elif self.instance and self.instance.pk and self.instance.start_date:
            start_date_value = self.instance.start_date.isoformat()
        elif self.initial.get('start_date'):
            start_date_value = self.initial['start_date'].isoformat() if hasattr(self.initial['start_date'], 'isoformat') else self.initial['start_date']

        if start_date_value:
            self.fields['end_date'].widget.attrs.update({'min': start_date_value})

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


class PlaceForm(forms.ModelForm):
    add_to_itinerary = forms.BooleanField(required=False)
    itinerary_title = forms.CharField(max_length=150, required=False)

    def __init__(self, *args, **kwargs):
        self.trip = kwargs.pop('trip', None)
        super().__init__(*args, **kwargs)

        # Check if this is an edit and has a visit_date, or if initial data has visit_date
        visit_date = None
        if self.instance and self.instance.pk:
            visit_date = self.instance.visit_date
        elif 'initial' in kwargs and 'visit_date' in kwargs['initial']:
            visit_date = kwargs['initial']['visit_date']

        # Auto-check the itinerary checkbox if a visit_date exists
        if visit_date:
            self.fields['add_to_itinerary'].initial = True

        if self.trip:
            min_date = self.trip.start_date.isoformat()
            max_date = self.trip.end_date.isoformat()
            self.fields['visit_date'].widget.attrs.update({'min': min_date, 'max': max_date})
            self.fields['return_date'].widget.attrs.update({'min': min_date, 'max': max_date})

    class Meta:
        model = Place
        fields = (
            'name',
            'place_type',
            'address',
            'latitude',
            'longitude',
            'visit_date',
            'return_date',
            'is_one_day_visit',
            'add_to_itinerary',
            'itinerary_title',
            'notes',
        )
        widgets = {
            'latitude': forms.NumberInput(attrs={'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'step': 'any'}),
            'visit_date': forms.DateInput(attrs={'type': 'date'}),
            'return_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        visit_date = cleaned_data.get('visit_date')
        return_date = cleaned_data.get('return_date')
        is_one_day_visit = cleaned_data.get('is_one_day_visit')

        if is_one_day_visit:
            if not visit_date:
                raise forms.ValidationError('Select a visit date when using one-day visit.')
            cleaned_data['return_date'] = visit_date
            return_date = visit_date

        if return_date and not visit_date:
            raise forms.ValidationError('Select a visit date before setting a return date.')

        if visit_date and return_date and return_date < visit_date:
            raise forms.ValidationError('Return date must be on or after visit date.')

        if self.trip and visit_date:
            if visit_date < self.trip.start_date or visit_date > self.trip.end_date:
                raise forms.ValidationError('Visit date must be within the trip dates.')

        if self.trip and return_date:
            if return_date < self.trip.start_date or return_date > self.trip.end_date:
                raise forms.ValidationError('Return date must be within the trip dates.')

        add_to_itinerary = cleaned_data.get('add_to_itinerary')
        itinerary_title = (cleaned_data.get('itinerary_title') or '').strip()
        
        # Auto-enable itinerary addition if visit_date exists
        if visit_date and not add_to_itinerary:
            add_to_itinerary = True
            cleaned_data['add_to_itinerary'] = True

        if add_to_itinerary and not visit_date:
            raise forms.ValidationError('Set a visit date when adding this place to itinerary.')

        if add_to_itinerary and not itinerary_title:
            place_name = (cleaned_data.get('name') or '').strip()
            cleaned_data['itinerary_title'] = f'Visit {place_name}' if place_name else 'Visit saved place'

        return cleaned_data


class TripRouteForm(forms.Form):
    route_name = forms.CharField(max_length=180, required=False)
    start_key = forms.ChoiceField(choices=[])
    end_key = forms.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        point_choices = kwargs.pop('point_choices', [])
        super().__init__(*args, **kwargs)
        self.fields['start_key'].choices = point_choices
        self.fields['end_key'].choices = point_choices

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('start_key') == cleaned_data.get('end_key'):
            raise forms.ValidationError('Start and end points must be different.')
        return cleaned_data


class AIItineraryHelpForm(forms.Form):
    TRAVEL_STYLE_CHOICES = [
        ('solo', 'Solo'),
        ('family', 'Family'),
        ('adventure', 'Adventure'),
        ('food', 'Food'),
        ('custom', 'Custom'),
    ]

    destination = forms.CharField(max_length=120)
    generate_from_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    generate_to_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    budget = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    travel_style = forms.ChoiceField(choices=TRAVEL_STYLE_CHOICES)
    custom_travel_style = forms.CharField(max_length=80, required=False)
    use_auto_weather = forms.BooleanField(required=False, initial=True)
    weather_summary = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
    preferred_start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    preferred_end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))

    def __init__(self, *args, **kwargs):
        self.trip = kwargs.pop('trip', None)
        super().__init__(*args, **kwargs)

        if self.trip and self.trip.start_date and self.trip.end_date and self.trip.start_date <= self.trip.end_date:
            min_date = self.trip.start_date.isoformat()
            max_date = self.trip.end_date.isoformat()
            self.fields['generate_from_date'].widget.attrs.update({'min': min_date, 'max': max_date})
            self.fields['generate_to_date'].widget.attrs.update({'min': min_date, 'max': max_date})

            if not self.is_bound:
                if not self.initial.get('generate_from_date'):
                    self.initial['generate_from_date'] = self.trip.start_date
                if not self.initial.get('generate_to_date'):
                    self.initial['generate_to_date'] = self.trip.end_date

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('preferred_start_time')
        end_time = cleaned_data.get('preferred_end_time')
        travel_style = cleaned_data.get('travel_style')
        custom_style = (cleaned_data.get('custom_travel_style') or '').strip()
        generate_from_date = cleaned_data.get('generate_from_date')
        generate_to_date = cleaned_data.get('generate_to_date')

        if not generate_from_date or not generate_to_date:
            raise forms.ValidationError('Select a valid date range for itinerary generation.')

        if generate_to_date < generate_from_date:
            raise forms.ValidationError('Generate to date must be on or after generate from date.')

        if self.trip and self.trip.start_date and self.trip.end_date:
            if generate_from_date < self.trip.start_date or generate_from_date > self.trip.end_date:
                raise forms.ValidationError('Generate from date must be within the trip range.')
            if generate_to_date < self.trip.start_date or generate_to_date > self.trip.end_date:
                raise forms.ValidationError('Generate to date must be within the trip range.')

        selected_dates = []
        current = generate_from_date
        while current <= generate_to_date:
            selected_dates.append(current.isoformat())
            current += timedelta(days=1)

        cleaned_data['selected_trip_dates'] = selected_dates

        if start_time and end_time and end_time <= start_time:
            raise forms.ValidationError('Preferred end time must be later than preferred start time.')

        if travel_style == 'custom' and not custom_style:
            raise forms.ValidationError('Add a custom travel style when selecting Custom.')

        if custom_style:
            cleaned_data['travel_style_text'] = custom_style
        else:
            cleaned_data['travel_style_text'] = travel_style

        return cleaned_data
