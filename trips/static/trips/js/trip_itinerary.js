(function () {
        const mapElement = document.getElementById('trip-map');
        const placeSearchInput = document.getElementById('place-search-input');
        const placeSuggestionsPanel = document.getElementById('place-suggestions');
        const placeSuggestionsList = document.getElementById('place-suggestions-list');
        const placeNameInput = document.getElementById('id_place-name');
        const placeAddressInput = document.getElementById('id_place-address');
        const placeLatitudeInput = document.getElementById('id_place-latitude');
        const placeLongitudeInput = document.getElementById('id_place-longitude');
        const placeVisitDateInput = document.getElementById('id_place-visit_date');
        const placeReturnDateInput = document.getElementById('id_place-return_date');
        const placeOneDayCheckbox = document.getElementById('id_place-is_one_day_visit');
        const addToItineraryCheckbox = document.getElementById('id_place-add_to_itinerary');
        const itineraryTitleRow = document.getElementById('itinerary-title-row');
        const itineraryTitleInput = document.getElementById('id_place-itinerary_title');

        // Initialize map if element exists
        if (mapElement) {
            const points = JSON.parse(document.getElementById('trip-map-points').textContent || '[]');
            const fallbackCenter = points.length ? [points[0].lat, points[0].lng] : [20, 0];
            const map = L.map('trip-map', { scrollWheelZoom: false }).setView(fallbackCenter, points.length ? 11 : 2);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap contributors',
            }).addTo(map);

            const bounds = [];
            points.forEach((point) => {
                const marker = L.marker([point.lat, point.lng]).addTo(map);
                marker.bindPopup(`<strong>${point.name}</strong><br>${point.address || ''}`.trim());
                bounds.push([point.lat, point.lng]);
            });

            if (bounds.length > 1) {
                map.fitBounds(bounds, { padding: [30, 30] });
            } else if (bounds.length === 1) {
                map.setView(bounds[0], 12);
            }

            let pickedLocationMarker = null;

            map.on('click', (event) => {
                if (!placeLatitudeInput || !placeLongitudeInput) {
                    return;
                }

                const { lat, lng } = event.latlng;
                placeLatitudeInput.value = Number(lat).toFixed(6);
                placeLongitudeInput.value = Number(lng).toFixed(6);

                if (pickedLocationMarker) {
                    pickedLocationMarker.setLatLng(event.latlng);
                } else {
                    pickedLocationMarker = L.circleMarker(event.latlng, {
                        radius: 6,
                        color: '#f4a259',
                        fillColor: '#f4a259',
                        fillOpacity: 0.95,
                    }).addTo(map);
                }
            });
        }

        // Place search functionality
        if (placeSearchInput) {
            placeSearchInput.addEventListener('input', function (e) {
                const query = e.target.value.trim();
                if (query.length < 2) {
                    placeSuggestionsPanel.style.display = 'none';
                    return;
                }

                fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=5`)
                    .then((res) => res.json())
                    .then((data) => {
                        placeSuggestionsList.innerHTML = '';
                        if (data.length === 0) {
                            placeSuggestionsPanel.style.display = 'none';
                            return;
                        }

                        data.forEach((place) => {
                            const li = document.createElement('li');
                            li.style.padding = '0.5rem 0';
                            li.style.cursor = 'pointer';
                            li.style.borderBottom = '1px solid #f0f0f0';
                            li.style.fontSize = '0.9rem';
                            li.textContent = place.display_name;

                            li.addEventListener('click', function () {
                                placeNameInput.value = place.name || place.display_name.split(',')[0];
                                placeAddressInput.value = place.display_name;
                                placeLatitudeInput.value = place.lat;
                                placeLongitudeInput.value = place.lon;
                                placeSearchInput.value = '';
                                placeSuggestionsPanel.style.display = 'none';
                            });

                            placeSuggestionsList.appendChild(li);
                        });
                        placeSuggestionsPanel.style.display = 'block';
                    })
                    .catch((err) => console.error('Search error:', err));
            });
        }

        // One-day visit sync
        function syncOneDayVisitState() {
            if (!placeOneDayCheckbox || !placeReturnDateInput) {
                return;
            }

            if (placeOneDayCheckbox.checked) {
                if (placeVisitDateInput && placeVisitDateInput.value) {
                    placeReturnDateInput.value = placeVisitDateInput.value;
                }
                placeReturnDateInput.disabled = true;
            } else {
                placeReturnDateInput.disabled = false;
            }
        }

        if (placeOneDayCheckbox) {
            placeOneDayCheckbox.addEventListener('change', syncOneDayVisitState);
            if (placeVisitDateInput) {
                placeVisitDateInput.addEventListener('change', syncOneDayVisitState);
            }
            syncOneDayVisitState();
        }

        // Itinerary title field visibility sync
        function syncItineraryTitleField() {
            if (!addToItineraryCheckbox || !itineraryTitleRow) {
                return;
            }

            if (addToItineraryCheckbox.checked) {
                itineraryTitleRow.classList.add('is-visible');
                itineraryTitleRow.setAttribute('aria-hidden', 'false');
                if (itineraryTitleInput) {
                    itineraryTitleInput.disabled = false;
                }
            } else {
                itineraryTitleRow.classList.remove('is-visible');
                itineraryTitleRow.setAttribute('aria-hidden', 'true');
                if (itineraryTitleInput) {
                    itineraryTitleInput.disabled = true;
                    itineraryTitleInput.value = '';
                }
            }
        }

        if (addToItineraryCheckbox) {
            addToItineraryCheckbox.addEventListener('change', syncItineraryTitleField);
            // Also sync when visit_date changes (auto-check checkbox if date is set)
            if (placeVisitDateInput) {
                placeVisitDateInput.addEventListener('change', function() {
                    if (placeVisitDateInput.value && !addToItineraryCheckbox.checked) {
                        addToItineraryCheckbox.checked = true;
                        syncItineraryTitleField();
                    }
                });
            }
            syncItineraryTitleField();
        }

        // Places section toggle functionality
        const toggleBtn = document.getElementById('places-toggle-btn');
        const placesContainer = document.getElementById('places-container');
        
        if (toggleBtn && placesContainer) {
            toggleBtn.addEventListener('click', function(e) {
                e.preventDefault();
                placesContainer.classList.toggle('collapsed');
                
                const isCollapsed = placesContainer.classList.contains('collapsed');
                const toggleText = toggleBtn.querySelector('.toggle-text');
                if (toggleText) {
                    toggleText.textContent = isCollapsed ? 'Show' : 'Hide';
                }
            });
        }
    })();
