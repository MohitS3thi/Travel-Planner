(function () {
        const searchButton = document.getElementById('destination-search-button');
        const destinationField = document.getElementById('id_destination');
        const latitudeField = document.getElementById('id_destination_lat');
        const longitudeField = document.getElementById('id_destination_lng');
        const startDateField = document.getElementById('id_start_date');
        const endDateField = document.getElementById('id_end_date');
        const status = document.getElementById('destination-search-status');
        const mapElement = document.getElementById('destination-picker-map');
        const suggestionsPanel = document.getElementById('destination-suggestions');
        const suggestionsList = document.getElementById('destination-suggestions-list');

        if (!searchButton || !destinationField || !latitudeField || !longitudeField || !status || !suggestionsPanel || !suggestionsList) {
            return;
        }

        let map = null;
        let mapMarker = null;
        let searchDebounceTimer = null;
        let lastRequestedQuery = '';
        let suggestionResults = [];

        function syncTripDateRange() {
            if (!startDateField || !endDateField) {
                return;
            }

            if (startDateField.value) {
                endDateField.min = startDateField.value;
                if (endDateField.value && endDateField.value < startDateField.value) {
                    endDateField.value = startDateField.value;
                }
            } else {
                endDateField.removeAttribute('min');
            }
        }

        if (startDateField && endDateField) {
            startDateField.addEventListener('change', syncTripDateRange);
            syncTripDateRange();
        }

        function hideSuggestions() {
            suggestionsPanel.style.display = 'none';
            suggestionsList.innerHTML = '';
        }

        function applyDestinationSelection(selection) {
            destinationField.value = selection.display_name;
            latitudeField.value = Number(selection.lat).toFixed(6);
            longitudeField.value = Number(selection.lon).toFixed(6);

            if (map) {
                const selected = [Number(selection.lat), Number(selection.lon)];
                if (mapMarker) {
                    mapMarker.setLatLng(selected);
                } else {
                    mapMarker = L.marker(selected).addTo(map);
                }
                map.setView(selected, 11);
            }
        }

        async function fetchSuggestions(query) {
            const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&q=${encodeURIComponent(query)}`, {
                headers: {
                    'Accept': 'application/json',
                },
            });
            return response.json();
        }

        function renderSuggestions(results) {
            suggestionsList.innerHTML = '';

            if (!results.length) {
                hideSuggestions();
                return;
            }

            results.forEach((result) => {
                const item = document.createElement('li');
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = result.display_name;
                button.className = 'button secondary';
                button.style.width = '100%';
                button.style.textAlign = 'left';
                button.style.marginBottom = '0.35rem';
                button.addEventListener('click', () => {
                    applyDestinationSelection(result);
                    status.textContent = 'Destination selected from recommendations.';
                    hideSuggestions();
                });
                item.appendChild(button);
                suggestionsList.appendChild(item);
            });

            suggestionsPanel.style.display = 'block';
        }

        destinationField.addEventListener('input', () => {
            const query = destinationField.value.trim();
            lastRequestedQuery = query;

            if (searchDebounceTimer) {
                clearTimeout(searchDebounceTimer);
            }

            if (query.length < 2) {
                hideSuggestions();
                return;
            }

            searchDebounceTimer = setTimeout(async () => {
                try {
                    const results = await fetchSuggestions(query);
                    if (lastRequestedQuery !== query) {
                        return;
                    }
                    suggestionResults = results;
                    renderSuggestions(results);
                } catch (error) {
                    hideSuggestions();
                }
            }, 300);
        });

        destinationField.addEventListener('blur', () => {
            setTimeout(() => {
                hideSuggestions();
            }, 120);
        });

        destinationField.addEventListener('focus', () => {
            if (suggestionResults.length) {
                renderSuggestions(suggestionResults);
            }
        });

        if (mapElement && typeof L !== 'undefined') {
            const initialLat = Number(latitudeField.value);
            const initialLng = Number(longitudeField.value);
            const hasInitialCoordinates = !Number.isNaN(initialLat) && !Number.isNaN(initialLng);
            const initialCenter = hasInitialCoordinates ? [initialLat, initialLng] : [20, 0];
            const initialZoom = hasInitialCoordinates ? 10 : 2;

            map = L.map('destination-picker-map', { scrollWheelZoom: false }).setView(initialCenter, initialZoom);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap contributors',
            }).addTo(map);

            if (hasInitialCoordinates) {
                mapMarker = L.marker(initialCenter).addTo(map);
            }

            map.on('click', (event) => {
                const { lat, lng } = event.latlng;
                latitudeField.value = Number(lat).toFixed(6);
                longitudeField.value = Number(lng).toFixed(6);

                if (mapMarker) {
                    mapMarker.setLatLng(event.latlng);
                } else {
                    mapMarker = L.marker(event.latlng).addTo(map);
                }

                status.textContent = 'Coordinates selected from map.';
            });
        }

        searchButton.addEventListener('click', async () => {
            const query = destinationField.value.trim();

            if (!query) {
                status.textContent = 'Enter a destination name first.';
                return;
            }

            status.textContent = 'Searching for coordinates...';
            searchButton.disabled = true;

            try {
                const results = suggestionResults.length ? suggestionResults : await fetchSuggestions(query);

                if (!results.length) {
                    status.textContent = 'No matches found. Try a more specific destination name.';
                    return;
                }

                const bestMatch = results[0];
                applyDestinationSelection(bestMatch);
                hideSuggestions();

                status.textContent = 'Coordinates loaded from OpenStreetMap search.';
            } catch (error) {
                status.textContent = 'Destination search failed. You can enter coordinates manually.';
            } finally {
                searchButton.disabled = false;
            }
        });
    })();
