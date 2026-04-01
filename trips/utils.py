def _season_for_month(month):
    if month in (12, 1, 2):
        return 'winter'
    if month in (3, 4, 5):
        return 'spring'
    if month in (6, 7, 8):
        return 'summer'
    return 'autumn'


def generate_weather_aware_suggestions(trip):
    season = _season_for_month(trip.start_date.month)

    season_tips = {
        'winter': [
            'Carry warm layers and waterproof shoes.',
            'Prioritize indoor attractions in case of snow or rain.',
            'Keep buffer time for transport delays caused by weather.',
        ],
        'spring': [
            'Pack a light jacket and compact umbrella for changing weather.',
            'Mix indoor and outdoor activities for flexibility.',
            'Book popular gardens and parks early for peak bloom periods.',
        ],
        'summer': [
            'Plan outdoor activities in early morning or late evening.',
            'Pack sunscreen, hat, and refillable water bottle.',
            'Add shaded indoor breaks during the hottest hours.',
        ],
        'autumn': [
            'Carry layers for cool mornings and evenings.',
            'Great season for scenic walks and photography.',
            'Keep rain-friendly backup options in your itinerary.',
        ],
    }

    interest_map = {
        'food': 'Include a local market food tour and reserve 1-2 signature restaurants.',
        'museum': 'Schedule museum visits during midday heat or rainy windows.',
        'hiking': 'Check trail conditions daily and start hikes early.',
        'nightlife': 'Plan a lighter schedule the morning after nightlife activities.',
        'shopping': 'Group shopping areas by neighborhood to reduce transit time.',
        'history': 'Book guided heritage walks for contextual local stories.',
    }

    suggestions = list(season_tips[season])

    lower_interests = trip.interests.lower()
    for key, recommendation in interest_map.items():
        if key in lower_interests:
            suggestions.append(recommendation)

    budget_hint = f'Your entered budget is {trip.budget}. Keep a 10-15% contingency for weather-related changes.'
    suggestions.append(budget_hint)

    return {
        'season': season,
        'tips': suggestions,
    }
