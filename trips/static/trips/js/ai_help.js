(function () {
        const autoWeatherCheckbox = document.getElementById('id_use_auto_weather');
        const weatherSummaryInput = document.getElementById('id_weather_summary');

        function syncWeatherSummaryState() {
            if (!autoWeatherCheckbox || !weatherSummaryInput) {
                return;
            }

            const isAuto = autoWeatherCheckbox.checked;
            weatherSummaryInput.readOnly = isAuto;
            weatherSummaryInput.style.opacity = isAuto ? '0.75' : '1';
        }

        if (autoWeatherCheckbox && weatherSummaryInput) {
            autoWeatherCheckbox.addEventListener('change', syncWeatherSummaryState);
            syncWeatherSummaryState();
        }
    })();
