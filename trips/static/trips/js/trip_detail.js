(function () {
        const mapElement = document.getElementById('trip-map');
        const routeStart = document.getElementById('id_start_key');
        const routeEnd = document.getElementById('id_end_key');
        const previewRouteButton = document.getElementById('preview-route-button');
        const clearRouteButton = document.getElementById('clear-route-button');
        const routeStatus = document.getElementById('route-status');
        const mapStatus = document.getElementById('map-status');
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
        const ribbonLinks = Array.from(document.querySelectorAll('#trip-detail-ribbon a[href^="#"]'));
        const revealItems = Array.from(document.querySelectorAll('.reveal-on-scroll'));

        if (!mapElement) {
            return;
        }

        const sectionTargets = ribbonLinks
            .map((link) => {
                const href = link.getAttribute('href');
                if (!href) {
                    return null;
                }
                return document.querySelector(href);
            })
            .filter(Boolean);

        function setActiveRibbonLink(sectionId) {
            ribbonLinks.forEach((link) => {
                const linkTarget = (link.getAttribute('href') || '').replace('#', '');
                if (linkTarget === sectionId) {
                    link.classList.add('active');
                } else {
                    link.classList.remove('active');
                }
            });
        }

        if (ribbonLinks.length) {
            const initialHash = window.location.hash.replace('#', '');
            setActiveRibbonLink(initialHash || 'trip-overview');

            ribbonLinks.forEach((link) => {
                link.addEventListener('click', () => {
                    const linkTarget = (link.getAttribute('href') || '').replace('#', '');
                    if (linkTarget) {
                        setActiveRibbonLink(linkTarget);
                    }
                });
            });

            if ('IntersectionObserver' in window && sectionTargets.length) {
                const ribbonObserver = new IntersectionObserver((entries) => {
                    const visibleSections = entries
                        .filter((entry) => entry.isIntersecting)
                        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

                    if (visibleSections.length) {
                        setActiveRibbonLink(visibleSections[0].target.id);
                    }
                }, {
                    root: null,
                    threshold: [0.2, 0.35, 0.55],
                    rootMargin: '-90px 0px -48% 0px',
                });

                sectionTargets.forEach((section) => ribbonObserver.observe(section));
            }
        }

        if (revealItems.length) {
            if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
                const revealObserver = new IntersectionObserver((entries, observer) => {
                    entries.forEach((entry) => {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('is-visible');
                            observer.unobserve(entry.target);
                        }
                    });
                }, {
                    threshold: 0.15,
                    rootMargin: '0px 0px -10% 0px',
                });

                revealItems.forEach((item) => revealObserver.observe(item));
            } else {
                revealItems.forEach((item) => item.classList.add('is-visible'));
            }
        }

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

        const points = JSON.parse(document.getElementById('trip-map-points').textContent || '[]');
        const lookup = new Map(points.map((point) => [point.key, point]));
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
        } else {
            mapStatus.textContent = 'Add destination coordinates or saved places to show markers on the map.';
        }

        const savedRouteLayers = [];
        let previewRouteLayers = [];
        let pickedLocationMarker = null;
        let placeSearchDebounceTimer = null;
        let placeLastQuery = '';
        let placeSuggestionResults = [];

        function computeBearing(startLat, startLng, endLat, endLng) {
            const toRadians = (value) => value * Math.PI / 180;
            const toDegrees = (value) => value * 180 / Math.PI;
            const phi1 = toRadians(startLat);
            const phi2 = toRadians(endLat);
            const deltaLambda = toRadians(endLng - startLng);

            const y = Math.sin(deltaLambda) * Math.cos(phi2);
            const x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(deltaLambda);
            return (toDegrees(Math.atan2(y, x)) + 360) % 360;
        }

        function createArrowMarker(startLat, startLng, endLat, endLng, color) {
            const arrowPositionFactor = 0.82;
            const markerLat = startLat + ((endLat - startLat) * arrowPositionFactor);
            const markerLng = startLng + ((endLng - startLng) * arrowPositionFactor);
            const bearing = computeBearing(startLat, startLng, endLat, endLng);

            return L.marker([markerLat, markerLng], {
                interactive: false,
                icon: L.divIcon({
                    className: 'route-arrow-icon',
                    html: `<div style="transform: rotate(${bearing}deg); color: ${color}; font-size: 18px; line-height: 1;">\u27A4</div>`,
                    iconSize: [18, 18],
                    iconAnchor: [9, 9],
                }),
            });
        }

        function drawRoute(startLat, startLng, endLat, endLng, options) {
            const line = L.polyline([
                [startLat, startLng],
                [endLat, endLng],
            ], {
                color: options.color,
                weight: options.weight,
                opacity: options.opacity,
                dashArray: options.dashArray || null,
            }).addTo(map);

            const arrow = createArrowMarker(startLat, startLng, endLat, endLng, options.color).addTo(map);
            return { line, arrow };
        }

        async function fetchPlaceSuggestions(query) {
            const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&q=${encodeURIComponent(query)}`, {
                headers: {
                    'Accept': 'application/json',
                },
            });
            return response.json();
        }

        function hidePlaceSuggestions() {
            if (!placeSuggestionsPanel || !placeSuggestionsList) {
                return;
            }
            placeSuggestionsPanel.style.display = 'none';
            placeSuggestionsList.innerHTML = '';
        }

        function applyPlaceSelection(selection) {
            if (placeNameInput) {
                const nameParts = (selection.display_name || '').split(',');
                placeNameInput.value = (nameParts[0] || selection.name || 'Selected place').trim();
            }
            if (placeAddressInput) {
                placeAddressInput.value = selection.display_name || '';
            }
            if (placeLatitudeInput) {
                placeLatitudeInput.value = Number(selection.lat).toFixed(6);
            }
            if (placeLongitudeInput) {
                placeLongitudeInput.value = Number(selection.lon).toFixed(6);
            }

            const selectedLatLng = [Number(selection.lat), Number(selection.lon)];
            if (pickedLocationMarker) {
                pickedLocationMarker.setLatLng(selectedLatLng);
            } else {
                pickedLocationMarker = L.circleMarker(selectedLatLng, {
                    radius: 6,
                    color: '#f4a259',
                    fillColor: '#f4a259',
                    fillOpacity: 0.95,
                }).addTo(map);
            }
            map.setView(selectedLatLng, Math.max(map.getZoom(), 12));
            routeStatus.textContent = 'Place details copied from recommendations.';
        }

        function renderPlaceSuggestions(results) {
            if (!placeSuggestionsPanel || !placeSuggestionsList) {
                return;
            }

            placeSuggestionsList.innerHTML = '';
            if (!results.length) {
                hidePlaceSuggestions();
                return;
            }

            results.forEach((result) => {
                const item = document.createElement('li');
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'button secondary';
                button.style.width = '100%';
                button.style.textAlign = 'left';
                button.style.marginBottom = '0.35rem';
                button.textContent = result.display_name;
                button.addEventListener('click', () => {
                    applyPlaceSelection(result);
                    hidePlaceSuggestions();
                });
                item.appendChild(button);
                placeSuggestionsList.appendChild(item);
            });

            placeSuggestionsPanel.style.display = 'block';
        }

        if (placeSearchInput && placeSuggestionsPanel && placeSuggestionsList) {
            placeSearchInput.addEventListener('input', () => {
                const query = placeSearchInput.value.trim();
                placeLastQuery = query;

                if (placeSearchDebounceTimer) {
                    clearTimeout(placeSearchDebounceTimer);
                }

                if (query.length < 2) {
                    hidePlaceSuggestions();
                    return;
                }

                placeSearchDebounceTimer = setTimeout(async () => {
                    try {
                        const results = await fetchPlaceSuggestions(query);
                        if (placeLastQuery !== query) {
                            return;
                        }
                        placeSuggestionResults = results;
                        renderPlaceSuggestions(results);
                    } catch (error) {
                        hidePlaceSuggestions();
                    }
                }, 300);
            });

            placeSearchInput.addEventListener('blur', () => {
                setTimeout(() => {
                    hidePlaceSuggestions();
                }, 120);
            });

            placeSearchInput.addEventListener('focus', () => {
                if (placeSuggestionResults.length) {
                    renderPlaceSuggestions(placeSuggestionResults);
                }
            });
        }

        function clearPreviewRoute() {
            previewRouteLayers.forEach((layer) => {
                map.removeLayer(layer.line);
                map.removeLayer(layer.arrow);
            });
            previewRouteLayers = [];
        }

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

            routeStatus.textContent = 'Picked map point copied to the place form coordinates.';
        });

        const savedRoutes = JSON.parse(document.getElementById('trip-routes-data').textContent || '[]');
        savedRoutes.forEach((route) => {
            const routeLayers = drawRoute(route.start_lat, route.start_lng, route.end_lat, route.end_lng, {
                color: route.color || '#2ca57e',
                weight: 4,
                opacity: 0.9,
            });
            routeLayers.line.bindPopup(`<strong>${route.name}</strong><br>${route.start_name} \u2192 ${route.end_name}`);
            savedRouteLayers.push(routeLayers);
        });

        previewRouteButton?.addEventListener('click', () => {
            const startPoint = lookup.get(routeStart.value);
            const endPoint = lookup.get(routeEnd.value);

            if (!startPoint || !endPoint) {
                routeStatus.textContent = 'Pick two saved points with coordinates first.';
                return;
            }

            clearPreviewRoute();
            const previewLayers = drawRoute(startPoint.lat, startPoint.lng, endPoint.lat, endPoint.lng, {
                color: '#f2be63',
                weight: 4,
                opacity: 0.95,
                dashArray: '10 6',
            });
            previewRouteLayers.push(previewLayers);

            map.fitBounds(previewLayers.line.getBounds(), { padding: [30, 30] });
            routeStatus.textContent = `Preview route from ${startPoint.name} to ${endPoint.name}. Click Create Route to save it.`;
        });

        clearRouteButton?.addEventListener('click', () => {
            clearPreviewRoute();
            routeStatus.textContent = 'Route preview cleared.';
        });
    })();
