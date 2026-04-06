import json
import os
import re
from pathlib import Path
from time import sleep
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _safe_time(value, fallback):
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        for fmt in ('%H:%M', '%H:%M:%S'):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
    return fallback


def _style_profile(style_text):
    style = (style_text or '').strip().lower()

    profiles = {
        'solo': {
            'morning_bias': 'cafe walk or neighborhood discovery',
            'afternoon_bias': 'high-interest landmark or local exploration',
            'evening_bias': 'light cultural stop and relaxed dinner',
            'activity_pct': Decimal('0.36'),
        },
        'family': {
            'morning_bias': 'kid-friendly activity with easy transit',
            'afternoon_bias': 'interactive museum or park break',
            'evening_bias': 'early dinner and low-effort evening stroll',
            'activity_pct': Decimal('0.30'),
        },
        'adventure': {
            'morning_bias': 'outdoor challenge while energy is highest',
            'afternoon_bias': 'second active block or viewpoint',
            'evening_bias': 'recovery meal and prep for next day',
            'activity_pct': Decimal('0.42'),
        },
        'food': {
            'morning_bias': 'signature breakfast or food market',
            'afternoon_bias': 'chef-led lunch or food street cluster',
            'evening_bias': 'reservation dinner with local specialties',
            'activity_pct': Decimal('0.26'),
        },
    }
    return profiles.get(style, {
        'morning_bias': 'easy start with a local highlight',
        'afternoon_bias': 'primary city experience',
        'evening_bias': 'slow evening with local flavor',
        'activity_pct': Decimal('0.34'),
    })


def _budget_split(total_budget, style_text):
    profile = _style_profile(style_text)
    activity_pct = profile['activity_pct']

    split = {
        'stay': Decimal('0.30'),
        'food': Decimal('0.25'),
        'activities': activity_pct,
        'transport': Decimal('0.12'),
    }
    split['buffer'] = Decimal('1.00') - sum(split.values())

    rounded = {}
    for key, pct in split.items():
        rounded[key] = {
            'percentage': int((pct * 100).quantize(Decimal('1'))),
            'amount': (total_budget * pct).quantize(Decimal('0.01')),
        }
    return rounded


def _weather_advice(weather_summary):
    text = (weather_summary or '').lower()

    if not text:
        return {
            'tempo': 'balanced',
            'guidance': 'Keep one indoor backup per day in case conditions change quickly.',
        }

    if any(keyword in text for keyword in ('rain', 'storm', 'thunder', 'showers')):
        return {
            'tempo': 'rain-aware',
            'guidance': 'Front-load indoor attractions in afternoon windows and keep rain-safe transport options.',
        }

    if any(keyword in text for keyword in ('hot', 'heat', 'sunny', 'humid')):
        return {
            'tempo': 'heat-aware',
            'guidance': 'Place outdoor plans in morning and move heavy walking to cooler evening blocks.',
        }

    if any(keyword in text for keyword in ('cold', 'snow', 'wind', 'chill')):
        return {
            'tempo': 'cold-aware',
            'guidance': 'Use shorter outdoor windows and include warm indoor anchors every day.',
        }

    return {
        'tempo': 'balanced',
        'guidance': 'Mix indoor and outdoor suggestions to keep the plan flexible.',
    }


def _build_place_pools(places):
    pools = {
        'morning': [],
        'afternoon': [],
        'evening': [],
    }

    for place in places:
        place_type = (getattr(place, 'place_type', '') or '').lower()

        if place_type in {'attraction', 'viewpoint'}:
            pools['morning'].append(place.name)
            pools['afternoon'].append(place.name)
        elif place_type in {'activity'}:
            pools['afternoon'].append(place.name)
        elif place_type in {'restaurant'}:
            pools['evening'].append(place.name)
            pools['afternoon'].append(place.name)
        elif place_type in {'hotel'}:
            pools['evening'].append(f'Check-in buffer around {place.name}')
        else:
            pools['morning'].append(place.name)

    return pools


def _pick_item(pool, fallback, day_index):
    if not pool:
        return fallback
    return pool[(day_index - 1) % len(pool)]


def _packing_suggestions(weather_summary, style_text):
    weather_text = (weather_summary or '').lower()
    style_text = (style_text or '').lower()

    suggestions = [
        'Carry digital and printed copies of IDs, bookings, and emergency contacts.',
        'Keep one power bank and a universal charging setup ready before departure.',
    ]

    if any(word in weather_text for word in ('rain', 'storm', 'showers')):
        suggestions.append('Pack a compact umbrella, waterproof pouch, and quick-dry layers.')
    if any(word in weather_text for word in ('hot', 'heat', 'sunny', 'humid')):
        suggestions.append('Pack breathable clothing, sunscreen, sunglasses, and a refillable bottle.')
    if any(word in weather_text for word in ('cold', 'snow', 'wind', 'chill')):
        suggestions.append('Pack thermal layers, gloves, and weatherproof walking shoes.')

    if 'adventure' in style_text:
        suggestions.append('Include a daypack, first-aid kit, and activity-specific safety gear.')
    if 'family' in style_text:
        suggestions.append('Keep snacks, basic medicines, and spare clothing in an easy-access bag.')
    if 'food' in style_text:
        suggestions.append('Reserve at least two high-demand restaurants in advance.')

    return suggestions


DEFAULT_OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_OPENAI_MODEL = 'gpt-4o-mini'


def _load_env_file_values():
    root = Path(__file__).resolve().parent.parent
    env_path = root / '.env'
    if not env_path.exists():
        return {}

    values = {}
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _get_openai_config():
    env_file_values = _load_env_file_values()
    api_key = (os.getenv('OPENAI_API_KEY') or env_file_values.get('OPENAI_API_KEY') or '').strip()
    api_url = (os.getenv('OPENAI_API_URL') or env_file_values.get('OPENAI_API_URL') or DEFAULT_OPENAI_API_URL).strip()
    model_name = (os.getenv('OPENAI_MODEL') or env_file_values.get('OPENAI_MODEL') or DEFAULT_OPENAI_MODEL).strip()

    timeout_text = (os.getenv('OPENAI_TIMEOUT_SECONDS') or env_file_values.get('OPENAI_TIMEOUT_SECONDS') or '').strip()
    if timeout_text.isdigit():
        timeout_seconds = max(10, int(timeout_text))
    elif 'localhost' in api_url or '127.0.0.1' in api_url:
        # Local models (e.g., Ollama) can take noticeably longer to answer.
        timeout_seconds = 120
    else:
        timeout_seconds = 25

    max_tokens_text = (os.getenv('OPENAI_MAX_TOKENS') or env_file_values.get('OPENAI_MAX_TOKENS') or '').strip()
    if max_tokens_text.isdigit():
        max_tokens = int(max_tokens_text)
    elif 'localhost' in api_url or '127.0.0.1' in api_url:
        # Local models often need more completion budget to emit fully closed JSON.
        max_tokens = 2200
    else:
        max_tokens = 1200

    return {
        'api_key': api_key,
        'api_url': api_url,
        'model_name': model_name,
        'timeout_seconds': timeout_seconds,
        'max_tokens': max_tokens,
        'is_local_endpoint': ('localhost' in api_url or '127.0.0.1' in api_url),
    }


def _extract_text_from_openai_payload(payload):
    def extract_from_content(content_value):
        if isinstance(content_value, str) and content_value.strip():
            return content_value.strip()

        if isinstance(content_value, dict):
            for key in ('text', 'content', 'output_text', 'response'):
                nested = content_value.get(key)
                extracted = extract_from_content(nested)
                if extracted:
                    return extracted
            return ''

        if isinstance(content_value, list):
            text_parts = []
            for item in content_value:
                extracted = extract_from_content(item)
                if extracted:
                    text_parts.append(extracted)
            joined = '\n'.join(text_parts).strip()
            return joined

        return ''

    choices = payload.get('choices') or []
    if choices:
        first_choice = choices[0] or {}
        message = first_choice.get('message') or {}
        content = message.get('content')

        extracted = extract_from_content(content)
        if extracted:
            return extracted

        reasoning = message.get('reasoning_content')
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning.strip()

        choice_text = first_choice.get('text')
        if isinstance(choice_text, str) and choice_text.strip():
            return choice_text.strip()

    message = payload.get('message') or {}
    if isinstance(message, dict):
        content = message.get('content')
        if isinstance(content, str) and content.strip():
            return content.strip()

    response_text = payload.get('response')
    if isinstance(response_text, str) and response_text.strip():
        return response_text.strip()

    extracted_top_level = extract_from_content(payload.get('content'))
    if extracted_top_level:
        return extracted_top_level

    top_text = payload.get('text')
    if isinstance(top_text, str) and top_text.strip():
        return top_text.strip()

    return ''


def _post_chat_completion(config, body_payload):
    timeout_seconds = config.get('request_timeout_seconds', config['timeout_seconds'])
    request = Request(
        config['api_url'],
        data=json.dumps(body_payload).encode('utf-8'),
        headers={
            'Authorization': f"Bearer {config['api_key']}",
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode('utf-8'))


def _post_text_completion(config, prompt_text):
    timeout_seconds = config.get('request_timeout_seconds', config['timeout_seconds'])
    completion_url = config['api_url']
    if completion_url.endswith('/chat/completions'):
        completion_url = completion_url[:-len('/chat/completions')] + '/completions'

    payload = {
        'model': config['model_name'],
        'prompt': prompt_text,
        'temperature': 0.4,
        'max_tokens': config['max_tokens'],
    }

    request = Request(
        completion_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f"Bearer {config['api_key']}",
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode('utf-8'))


def _is_timeout_error(exc):
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, URLError):
        reason = getattr(exc, 'reason', None)
        reason_text = str(reason or exc).lower()
        return 'timed out' in reason_text or 'timeout' in reason_text
    return False


def _repair_json_with_model(config, malformed_text):
    repair_payload = {
        'model': config['model_name'],
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You are a JSON repair utility. Return strict valid JSON only. '
                    'Do not add markdown, prose, or comments. Keep original fields and values where possible.'
                ),
            },
            {
                'role': 'user',
                'content': malformed_text,
            },
        ],
        'temperature': 0,
        'max_tokens': max(400, min(config['max_tokens'], 2000)),
    }

    if not config['is_local_endpoint']:
        repair_payload['response_format'] = {'type': 'json_object'}

    repaired_response = _post_chat_completion(config, repair_payload)
    repaired_text = _extract_text_from_openai_payload(repaired_response)
    return _parse_json_from_model_text(repaired_text)


def _parse_json_from_model_text(text):
    def extract_first_balanced_json_object(raw_text):
        start = raw_text.find('{')
        if start == -1:
            return None

        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(raw_text)):
            char = raw_text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return raw_text[start:index + 1]

        return None

    if not text:
        raise RuntimeError('Model returned empty text content.')

    cleaned = text.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.strip('`').strip()
        if cleaned.lower().startswith('json'):
            cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    balanced = extract_first_balanced_json_object(cleaned)
    if balanced:
        try:
            return json.loads(balanced)
        except json.JSONDecodeError:
            pass

    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    if cleaned.strip().startswith('{') and cleaned.count('{') > cleaned.count('}'):
        raise RuntimeError('Model JSON appears truncated. Increase OPENAI_MAX_TOKENS or timeout for local model.')

    preview = cleaned[:220].replace('\n', ' ')
    raise RuntimeError(f'Model response was not valid JSON. Preview: {preview}')


def _decimal_to_text(value):
    try:
        return str(Decimal(str(value)).quantize(Decimal('0.01')))
    except Exception:
        return '0.00'


def _to_decimal(value, default='0.00'):
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except Exception:
        return Decimal(default)


def _clean_generated_text(value):
    text = str(value or '')
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'\/?think\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalize_selected_trip_dates(selected_trip_dates):
    normalized_dates = []
    for value in selected_trip_dates or []:
        if isinstance(value, date):
            normalized_dates.append(value)
            continue
        if isinstance(value, str):
            try:
                normalized_dates.append(datetime.strptime(value, '%Y-%m-%d').date())
            except ValueError:
                continue
    unique_sorted_dates = sorted(set(normalized_dates))
    return unique_sorted_dates


def _prorated_budget(total_budget, selected_days_count, total_trip_days):
    budget_value = Decimal(str(total_budget or 0)).quantize(Decimal('0.01'))
    selected_days = max(1, int(selected_days_count or 1))
    trip_days = int(total_trip_days or 0)

    if trip_days <= 0:
        return budget_value

    capped_selected_days = min(selected_days, trip_days)
    ratio = Decimal(capped_selected_days) / Decimal(trip_days)
    prorated = (budget_value * ratio).quantize(Decimal('0.01'))
    return max(prorated, Decimal('0.00'))


def _sanitize_live_plan(plan, destination, selected_trip_dates, preferred_start_time, preferred_end_time, travel_style):
    normalized_dates = _normalize_selected_trip_dates(selected_trip_dates)
    days_target = len(normalized_dates)
    if days_target <= 0:
        days_target = max(1, int((plan.get('summary') or {}).get('days') or 1))
    start_time = _safe_time(preferred_start_time, time(8, 0))
    end_time = _safe_time(preferred_end_time, time(21, 0))
    if end_time <= start_time:
        end_time = (datetime.combine(datetime.today(), start_time) + timedelta(hours=10)).time()

    morning_end = (datetime.combine(datetime.today(), start_time) + timedelta(hours=4)).time()
    afternoon_end = (datetime.combine(datetime.today(), start_time) + timedelta(hours=8)).time()
    default_windows = {
        'morning_window': f'{start_time.strftime("%H:%M")} - {morning_end.strftime("%H:%M")}',
        'afternoon_window': f'{morning_end.strftime("%H:%M")} - {afternoon_end.strftime("%H:%M")}',
        'evening_window': f'{afternoon_end.strftime("%H:%M")} - {end_time.strftime("%H:%M")}',
    }

    existing_days = list(plan.get('day_wise_itinerary') or [])
    remaining_budget = _to_decimal(plan.get('remaining_planning_budget', '0.00'))
    per_day_budget = (remaining_budget / Decimal(days_target)).quantize(Decimal('0.01')) if days_target else Decimal('0.00')
    default_morning_budget = (per_day_budget * Decimal('0.28')).quantize(Decimal('0.01'))
    default_afternoon_budget = (per_day_budget * Decimal('0.46')).quantize(Decimal('0.01'))
    default_evening_budget = (per_day_budget - default_morning_budget - default_afternoon_budget).quantize(Decimal('0.01'))

    sanitized_days = []
    for index in range(days_target):
        source_day = existing_days[index] if index < len(existing_days) and isinstance(existing_days[index], dict) else {}
        day_number = source_day.get('day_number') or (index + 1)
        try:
            day_number = int(day_number)
        except (TypeError, ValueError):
            day_number = index + 1

        trip_date = None
        if index < len(normalized_dates):
            trip_date = normalized_dates[index].isoformat()
        else:
            source_trip_date = source_day.get('trip_date')
            if isinstance(source_trip_date, str):
                trip_date = source_trip_date

        morning_text = _clean_generated_text(source_day.get('morning'))
        afternoon_text = _clean_generated_text(source_day.get('afternoon'))
        evening_text = _clean_generated_text(source_day.get('evening'))

        if not morning_text:
            morning_text = f'{destination}: Start with a scenic neighborhood walk and coffee spot.'
        if not afternoon_text:
            afternoon_text = f'{destination}: Plan a core sightseeing block or local activity.'
        if not evening_text:
            evening_text = f'{destination}: Keep a relaxed dinner and local culture stop.'

        budget_block = source_day.get('budget') if isinstance(source_day.get('budget'), dict) else {}
        morning_budget = _to_decimal(budget_block.get('morning', default_morning_budget))
        afternoon_budget = _to_decimal(budget_block.get('afternoon', default_afternoon_budget))
        evening_budget = _to_decimal(budget_block.get('evening', default_evening_budget))
        total_budget = _to_decimal(budget_block.get('total', morning_budget + afternoon_budget + evening_budget))

        if total_budget <= Decimal('0.00'):
            morning_budget = default_morning_budget
            afternoon_budget = default_afternoon_budget
            evening_budget = default_evening_budget
            total_budget = per_day_budget

        morning_window = _clean_generated_text(source_day.get('morning_window')) or default_windows['morning_window']
        afternoon_window = _clean_generated_text(source_day.get('afternoon_window')) or default_windows['afternoon_window']
        evening_window = _clean_generated_text(source_day.get('evening_window')) or default_windows['evening_window']

        sanitized_days.append({
            'day_number': day_number,
            'trip_date': trip_date,
            'morning_window': morning_window,
            'afternoon_window': afternoon_window,
            'evening_window': evening_window,
            'morning': morning_text,
            'afternoon': afternoon_text,
            'evening': evening_text,
            'budget': {
                'morning': _decimal_to_text(morning_budget),
                'afternoon': _decimal_to_text(afternoon_budget),
                'evening': _decimal_to_text(evening_budget),
                'total': _decimal_to_text(total_budget),
            },
        })

    plan['day_wise_itinerary'] = sanitized_days

    split_values = plan.get('budget_split') if isinstance(plan.get('budget_split'), dict) else {}
    if all(_to_decimal((split_values.get(key) or {}).get('amount', '0.00')) <= Decimal('0.00') for key in ('stay', 'food', 'activities', 'transport', 'buffer')):
        plan['budget_split'] = _budget_split(remaining_budget, travel_style)

    packing = plan.get('packing_suggestions')
    if not isinstance(packing, list) or not any(_clean_generated_text(item) for item in packing):
        weather_summary = ((plan.get('summary') or {}).get('weather_summary') or '')
        plan['packing_suggestions'] = _packing_suggestions(weather_summary, travel_style)

    summary = plan.get('summary') if isinstance(plan.get('summary'), dict) else {}
    summary['destination'] = summary.get('destination') or destination
    summary['days'] = days_target
    summary['travel_style'] = summary.get('travel_style') or travel_style
    if not _clean_generated_text(summary.get('weather_guidance')):
        summary['weather_guidance'] = _weather_advice(summary.get('weather_summary') or '').get('guidance')
    plan['summary'] = summary

    return plan


def _place_snapshot(place):
    return {
        'name': getattr(place, 'name', ''),
        'place_type': getattr(place, 'place_type', ''),
        'address': getattr(place, 'address', ''),
        'notes': getattr(place, 'notes', ''),
        'visit_date': getattr(place, 'visit_date', None).isoformat() if getattr(place, 'visit_date', None) else None,
        'return_date': getattr(place, 'return_date', None).isoformat() if getattr(place, 'return_date', None) else None,
    }


def _itinerary_item_snapshot(item):
    return {
        'date': getattr(item, 'date', None).isoformat() if getattr(item, 'date', None) else None,
        'title': getattr(item, 'title', ''),
        'notes': getattr(item, 'notes', ''),
        'estimated_cost': _decimal_to_text(getattr(item, 'estimated_cost', 0)),
    }


def _build_llm_prompt(destination, days, total_budget, travel_style, weather_summary, preferred_start_time, preferred_end_time, saved_places, existing_itinerary_items):
    places = [_place_snapshot(place) for place in saved_places]
    items = [_itinerary_item_snapshot(item) for item in existing_itinerary_items]
    available_budget = total_budget - sum((Decimal(str(item.get('estimated_cost', '0'))).quantize(Decimal('0.01')) for item in items), Decimal('0.00'))
    if available_budget < 0:
        available_budget = Decimal('0.00')

    return {
        'destination': destination,
        'number_of_days': days,
        'selected_trip_dates': [],
        'total_budget': _decimal_to_text(total_budget),
        'available_budget_after_existing_items': _decimal_to_text(available_budget),
        'travel_style': travel_style,
        'weather_summary': weather_summary or '',
        'preferred_start_time': preferred_start_time.strftime('%H:%M') if hasattr(preferred_start_time, 'strftime') else str(preferred_start_time),
        'preferred_end_time': preferred_end_time.strftime('%H:%M') if hasattr(preferred_end_time, 'strftime') else str(preferred_end_time),
        'saved_places': places,
        'existing_itinerary_items': items,
    }


def _normalize_plan_payload(payload, destination, travel_style, available_budget):
    def normalize_budget_entry(raw_value):
        if isinstance(raw_value, dict):
            percentage = raw_value.get('percentage') or 0
            amount = raw_value.get('amount', '0')
        elif isinstance(raw_value, (int, float, Decimal)):
            # If model returns a bare number, treat it as amount with unknown percentage.
            percentage = 0
            amount = raw_value
        elif isinstance(raw_value, str):
            # If model returns a bare string like "1200" or "1200.50".
            percentage = 0
            amount = raw_value
        else:
            percentage = 0
            amount = '0'

        try:
            percentage_int = int(float(str(percentage)))
        except (TypeError, ValueError):
            percentage_int = 0

        return {
            'percentage': percentage_int,
            'amount': _decimal_to_text(amount),
        }

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}

    config = _get_openai_config()
    days = payload.get('day_wise_itinerary') or payload.get('days') or []
    if isinstance(days, dict):
        days = list(days.values())
    if not isinstance(days, list):
        days = []

    normalized_days = []
    for index, day in enumerate(days, start=1):
        if not isinstance(day, dict):
            continue
        budget = day.get('budget') or {}
        if not isinstance(budget, dict):
            budget = {}

        day_number_raw = day.get('day_number') or index
        try:
            day_number_value = int(day_number_raw)
        except (TypeError, ValueError):
            day_number_value = index

        normalized_days.append({
            'day_number': day_number_value,
            'trip_date': day.get('trip_date') or None,
            'morning_window': day.get('morning_window') or '',
            'afternoon_window': day.get('afternoon_window') or '',
            'evening_window': day.get('evening_window') or '',
            'morning': day.get('morning') or '',
            'afternoon': day.get('afternoon') or '',
            'evening': day.get('evening') or '',
            'budget': {
                'morning': _decimal_to_text(budget.get('morning', '0')),
                'afternoon': _decimal_to_text(budget.get('afternoon', '0')),
                'evening': _decimal_to_text(budget.get('evening', '0')),
                'total': _decimal_to_text(budget.get('total', '0')),
            },
        })

    budget_split = payload.get('budget_split') or {}
    if not isinstance(budget_split, dict):
        budget_split = {}

    normalized_budget_split = {}
    for key in ('stay', 'food', 'activities', 'transport', 'buffer'):
        normalized_budget_split[key] = normalize_budget_entry(budget_split.get(key, {}))

    packing_suggestions = payload.get('packing_suggestions') or []
    if not isinstance(packing_suggestions, list):
        packing_suggestions = []

    summary = payload.get('summary') or {}
    if not isinstance(summary, dict):
        summary = {}

    summary_days_raw = summary.get('days')
    try:
        summary_days = int(summary_days_raw or len(normalized_days) or 1)
    except (TypeError, ValueError):
        summary_days = len(normalized_days) or 1

    return {
        'summary': {
            'destination': summary.get('destination') or destination,
            'days': summary_days,
            'travel_style': summary.get('travel_style') or travel_style,
            'weather_summary': summary.get('weather_summary') or '',
            'weather_guidance': summary.get('weather_guidance') or '',
            'model_name': summary.get('model_name') or config['model_name'],
            'source': summary.get('source') or 'live-model',
        },
        'day_wise_itinerary': normalized_days,
        'budget_split': normalized_budget_split,
        'packing_suggestions': packing_suggestions,
        'source': 'live-model',
    }


def _call_live_model(prompt_payload):
    config = _get_openai_config()
    api_key = config['api_key']
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not set (neither environment variable nor .env file).')

    max_retries = 2
    retry_override = (os.getenv('OPENAI_MAX_RETRIES') or '').strip()
    if retry_override.isdigit():
        max_retries = max(0, int(retry_override))

    system_prompt = (
        'You are a travel itinerary planner. Return valid JSON only. '
        'Create a day-wise itinerary using the provided trip inputs, saved places, weather context, and available budget. '
        'Keep morning, afternoon, and evening suggestions concise and practical. '
        'Include rough budget split and packing suggestions. '
        'Use the response shape exactly as: {"summary": {...}, "day_wise_itinerary": [...], "budget_split": {...}, "packing_suggestions": [...]}.'
    )

    user_prompt = json.dumps(prompt_payload, ensure_ascii=True)
    body_payload = {
        'model': config['model_name'],
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': 0.5,
        'max_tokens': config['max_tokens'],
    }

    if not config['is_local_endpoint']:
        body_payload['response_format'] = {'type': 'json_object'}

    payload = None
    requested_days = 1
    try:
        requested_days = max(1, int(prompt_payload.get('number_of_days') or 1))
    except (TypeError, ValueError):
        requested_days = 1

    base_timeout = int(config.get('timeout_seconds') or 25)
    timeout_step = 25 if config['is_local_endpoint'] else 10
    adaptive_timeout = base_timeout + (max(0, requested_days - 1) * timeout_step)

    for attempt in range(max_retries + 1):
        config['request_timeout_seconds'] = adaptive_timeout + (attempt * timeout_step)
        try:
            payload = _post_chat_completion(config, body_payload)
            break
        except HTTPError as exc:
            error_detail = ''
            try:
                raw_error = exc.read().decode('utf-8')
                parsed_error = json.loads(raw_error)
                error_detail = ((parsed_error.get('error') or {}).get('message') or '').strip()
            except Exception:
                error_detail = ''

            if exc.code == 429 and attempt < max_retries:
                retry_after = exc.headers.get('Retry-After') if exc.headers else None
                if retry_after and retry_after.isdigit():
                    sleep_seconds = max(1, int(retry_after))
                else:
                    sleep_seconds = 1 + attempt
                sleep(sleep_seconds)
                continue

            if exc.code == 429:
                message = error_detail or 'Too many requests or insufficient quota.'
                raise RuntimeError(f'HTTP 429 from OpenAI: {message}')

            message = error_detail or str(exc)
            raise RuntimeError(f'HTTP {exc.code} from OpenAI: {message}')
        except (TimeoutError, URLError) as exc:
            if _is_timeout_error(exc) and attempt < max_retries:
                sleep(1 + attempt)
                continue
            if _is_timeout_error(exc):
                raise RuntimeError(
                    'Live model timed out. Try a shorter date range or increase OPENAI_TIMEOUT_SECONDS in .env.'
                )
            raise RuntimeError(f'Network error while calling live model: {exc}')

    config.pop('request_timeout_seconds', None)

    if payload is None:
        raise RuntimeError('OpenAI response was empty after retries.')

    model_text = _extract_text_from_openai_payload(payload)
    if not model_text and config['is_local_endpoint']:
        fallback_prompt = (
            'Return valid JSON only with keys: summary, day_wise_itinerary, budget_split, packing_suggestions. '
            'Use this trip context: ' + user_prompt
        )
        config['request_timeout_seconds'] = adaptive_timeout + (max_retries * timeout_step)
        completion_payload = _post_text_completion(config, fallback_prompt)
        config.pop('request_timeout_seconds', None)
        model_text = _extract_text_from_openai_payload(completion_payload)

    try:
        parsed = _parse_json_from_model_text(model_text)
    except RuntimeError:
        parsed = _repair_json_with_model(config, model_text)
    return parsed


def _generate_live_itinerary(*, destination, selected_trip_dates, budget, total_trip_days, travel_style, weather_summary, preferred_start_time, preferred_end_time, saved_places, existing_itinerary_items):
    normalized_dates = _normalize_selected_trip_dates(selected_trip_dates)
    days = len(normalized_dates) if normalized_dates else 1
    total_budget = _prorated_budget(budget, days, total_trip_days)
    prompt_payload = _build_llm_prompt(
        destination,
        days,
        total_budget,
        travel_style,
        weather_summary,
        preferred_start_time,
        preferred_end_time,
        saved_places,
        existing_itinerary_items,
    )
    prompt_payload['selected_trip_dates'] = [value.isoformat() for value in normalized_dates]

    live_payload = _call_live_model(prompt_payload)
    plan = _normalize_plan_payload(live_payload, destination, travel_style, prompt_payload['available_budget_after_existing_items'])
    plan['committed_cost'] = sum((item.estimated_cost for item in existing_itinerary_items), Decimal('0.00'))
    plan['remaining_planning_budget'] = Decimal(str(prompt_payload['available_budget_after_existing_items']))
    plan['source'] = 'live-model'
    plan = _sanitize_live_plan(
        plan,
        destination,
        normalized_dates,
        preferred_start_time,
        preferred_end_time,
        travel_style,
    )
    return plan


def _generate_rule_based_itinerary(*, destination, selected_trip_dates, budget, total_trip_days, travel_style, weather_summary, preferred_start_time, preferred_end_time, saved_places, existing_itinerary_items):
    normalized_dates = _normalize_selected_trip_dates(selected_trip_dates)
    days = len(normalized_dates) if normalized_dates else 1
    total_budget = _prorated_budget(budget, days, total_trip_days)
    style_profile = _style_profile(travel_style)
    weather_profile = _weather_advice(weather_summary)

    start_time = _safe_time(preferred_start_time, time(8, 0))
    end_time = _safe_time(preferred_end_time, time(21, 0))

    if end_time <= start_time:
        end_time = (datetime.combine(datetime.today(), start_time) + timedelta(hours=10)).time()

    morning_end = (datetime.combine(datetime.today(), start_time) + timedelta(hours=4)).time()
    afternoon_end = (datetime.combine(datetime.today(), start_time) + timedelta(hours=8)).time()

    place_pools = _build_place_pools(saved_places)

    per_day_budget = (total_budget / days).quantize(Decimal('0.01')) if days else Decimal('0.00')
    morning_budget = (per_day_budget * Decimal('0.28')).quantize(Decimal('0.01'))
    afternoon_budget = (per_day_budget * Decimal('0.46')).quantize(Decimal('0.01'))
    evening_budget = (per_day_budget - morning_budget - afternoon_budget).quantize(Decimal('0.01'))

    generated_days = []
    for day_index in range(1, days + 1):
        trip_date = normalized_dates[day_index - 1].isoformat() if day_index - 1 < len(normalized_dates) else None
        morning_place = _pick_item(place_pools['morning'], f"{destination}: {style_profile['morning_bias']}", day_index)
        afternoon_place = _pick_item(place_pools['afternoon'], f"{destination}: {style_profile['afternoon_bias']}", day_index)
        evening_place = _pick_item(place_pools['evening'], f"{destination}: {style_profile['evening_bias']}", day_index)

        if weather_profile['tempo'] == 'rain-aware' and day_index % 2 == 0:
            afternoon_place = f'Indoor-focused block near {destination} center'
        if weather_profile['tempo'] == 'heat-aware' and day_index % 2 == 1:
            afternoon_place = f'Low-exposure indoor break and recharge in {destination}'

        generated_days.append({
            'day_number': day_index,
            'trip_date': trip_date,
            'morning_window': f'{start_time.strftime("%H:%M")} - {morning_end.strftime("%H:%M")}',
            'afternoon_window': f'{morning_end.strftime("%H:%M")} - {afternoon_end.strftime("%H:%M")}',
            'evening_window': f'{afternoon_end.strftime("%H:%M")} - {end_time.strftime("%H:%M")}',
            'morning': morning_place,
            'afternoon': afternoon_place,
            'evening': evening_place,
            'budget': {
                'morning': morning_budget,
                'afternoon': afternoon_budget,
                'evening': evening_budget,
                'total': per_day_budget,
            },
        })

    existing_committed = sum((item.estimated_cost for item in existing_itinerary_items), Decimal('0.00'))
    recommended_budget = max(total_budget - existing_committed, Decimal('0.00'))

    return {
        'summary': {
            'destination': destination,
            'days': days,
            'travel_style': travel_style,
            'weather_summary': weather_summary,
            'weather_guidance': weather_profile['guidance'],
            'model_name': 'rule-based-fallback',
            'source': 'fallback-rule-engine',
        },
        'day_wise_itinerary': generated_days,
        'budget_split': _budget_split(recommended_budget, travel_style),
        'packing_suggestions': _packing_suggestions(weather_summary, travel_style),
        'committed_cost': existing_committed,
        'remaining_planning_budget': recommended_budget,
        'source': 'fallback-rule-engine',
    }


def generate_personalized_itinerary(*, destination, selected_trip_dates, budget, total_trip_days, travel_style, weather_summary, preferred_start_time, preferred_end_time, saved_places, existing_itinerary_items):
    try:
        return _generate_live_itinerary(
            destination=destination,
            selected_trip_dates=selected_trip_dates,
            budget=budget,
            total_trip_days=total_trip_days,
            travel_style=travel_style,
            weather_summary=weather_summary,
            preferred_start_time=preferred_start_time,
            preferred_end_time=preferred_end_time,
            saved_places=saved_places,
            existing_itinerary_items=existing_itinerary_items,
        )
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        fallback_plan = _generate_rule_based_itinerary(
            destination=destination,
            selected_trip_dates=selected_trip_dates,
            budget=budget,
            total_trip_days=total_trip_days,
            travel_style=travel_style,
            weather_summary=weather_summary,
            preferred_start_time=preferred_start_time,
            preferred_end_time=preferred_end_time,
            saved_places=saved_places,
            existing_itinerary_items=existing_itinerary_items,
        )
        fallback_plan['summary']['fallback_reason'] = str(exc)
        return fallback_plan
