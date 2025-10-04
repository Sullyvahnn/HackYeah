var map = L.map('map').setView([50.0647, 19.9450], 13);
var alertMode = false;
var selectedLocation = null;
var tempMarker = null;
var tempCircle = null;
var heatmapLayer = null;
var useMarkers = [];
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
    }).addTo(map);
function loadAllAlerts() {
    fetch("/api/reports")
        .then(res => {
            if (!res.ok) {
                throw new Error('Network response was not ok');
            }
            return res.json();
        })
        .then(data => {
            // Usuń stare markery
            userMarkers.forEach(item => {
                map.removeLayer(item.marker);
                map.removeLayer(item.circle);
            });
            userMarkers = [];

            // Dodaj nowe markery
            data.forEach(alert => {
                if (alert.coordinates && Array.isArray(alert.coordinates)) {
                    var latlng = [alert.coordinates[0], alert.coordinates[1]];

                    // Dodaj marker
                    var marker = L.marker(latlng).addTo(map)
                        .bindPopup(`
                            <b>${alert.label || 'Alert'}</b><br>
                            Data: ${alert.date}<br>
                            ${alert.user_email ? `Użytkownik: ${alert.user_email}` : ''}
                        `);

                    // Dodaj okrąg
                    var circle = L.circle(latlng, {
                        radius: 50,
                        color: 'red',
                        fillColor: '#f03',
                        fillOpacity: 0.2
                    }).addTo(map);

                    // Zapisz referencje
                    userMarkers.push({
                        marker: marker,
                        circle: circle,
                        id: alert.id
                    });
                }
            });
        })
        .catch(error => {
            console.error("Błąd podczas ładowania alertów:", error);
        });
}
function getHeatColor(value, min, max) {
    var normalized = (value - min) / (max - min);

    if (normalized < 0.25) {
        var alpha = normalized * 4;
        return `rgba(255, 255, 0, ${alpha * 0.8})`; // stronger transparency
    } else if (normalized < 0.5) {
        var t = (normalized - 0.25) * 4;
        return `rgba(255, ${255 - t * 128}, 0, ${0.7 + t * 0.3})`;
    } else if (normalized < 0.75) {
        var t = (normalized - 0.5) * 4;
        return `rgba(255, ${127 - t * 127}, 0, ${0.9})`;
    } else {
        var t = (normalized - 0.75) * 4;
        return `rgba(${255 - t * 55}, 0, 0, 1)`; // full opacity
    }
}

function drawHeatmapCanvas(heatmapData, bounds) {
    var canvas = document.createElement('canvas');
    var resolution = heatmapData.grid_info.resolution;
    canvas.width = resolution;
    canvas.height = resolution;

    var ctx = canvas.getContext('2d');
    var grid = heatmapData.heatmap;

    // Find min and max values for color scaling
    var flatGrid = grid.flat();
    var maxValue = Math.max(...flatGrid);
    var minValue = Math.min(...flatGrid.filter(v => v > 0));

    if (minValue === undefined || minValue === Infinity) {
        minValue = 0;
    }

    // Draw each cell
    for (var i = 0; i < resolution; i++) {
        for (var j = 0; j < resolution; j++) {
            var value = grid[i][j];

            if (value > 0) {
                ctx.fillStyle = getHeatColor(value, minValue, maxValue);
                ctx.fillRect(j, resolution - 1 - i, 1, 1);
            }
        }
    }

    return canvas;
}

// Function to load and display heatmap
function loadHeatmap() {
    fetch('/api/heatmap')
        .then(res => res.json())
        .then(response => {
            if (response.status !== 'ok') {
                console.error('Failed to load heatmap:', response.message);
                return;
            }
            console.log(response.data);

            var data = response.data;
            var bounds = data.bounds;

            // Create canvas with heatmap
            var canvas = drawHeatmapCanvas(data, bounds);

            // Remove old heatmap layer if exists
            if (heatmapLayer) {
                map.removeLayer(heatmapLayer);
            }

            // Create image overlay from canvas
            var imageBounds = [
                [bounds.min_lat, bounds.min_lon],
                [bounds.max_lat, bounds.max_lon]
            ];

            heatmapLayer = L.imageOverlay(canvas.toDataURL(), imageBounds, {
                opacity: 0.7,
                interactive: false,
                pane: 'overlayPane',
                zIndex: 400
            }).addTo(map);

            // Force the layer to be on top
            if (heatmapLayer.getElement()) {
                heatmapLayer.getElement().style.zIndex = 400;
            }

            console.log('Heatmap loaded successfully');
        })
        .catch(error => {
            console.error('Error loading heatmap:', error);
        });
}
    // --- MENU TOGGLE ---
    function toggleMenu() {
        document.getElementById('menu').classList.toggle('open');
    }

    // --- ZAMKNIJ MENU I WRÓĆ DO MAPY ---
    function closeMenuAndReturnToMap() {
        document.getElementById('menu').classList.remove('open');
        map.getContainer().focus();
    }

    // --- ALERT MODE - CZĘŚĆ 1: WYBÓR LOKALIZACJI ---
    function enableAlertMode() {
      // alert('{{user_email}}')
        if (!'{{user_email}}') {
            // alert("Musisz być zalogowany, aby dodać alert.");
            return;
        }

        alertMode = true;
        selectedLocation = null; // Resetuj poprzedni wybór

        // Usuń poprzednie tymczasowe elementy
        if (tempMarker) {
            map.removeLayer(tempMarker);
            tempMarker = null;
        }
        if (tempCircle) {
            map.removeLayer(tempCircle);
            tempCircle = null;
        }

        toggleMenu();
        // alert("Kliknij na mapie, aby wybrać lokalizację alertu.");
    }

    // --- OBSŁUGA KLIKNIĘCIA NA MAPIE - CZĘŚĆ 1: ZAZNACZANIE ---
    map.on('click', function(e) {
        if (!alertMode) return;

        var latlng = e.latlng;
        selectedLocation = latlng; // Zapisz współrzędne do późniejszego użycia

        // Usuń poprzednie tymczasowe elementy
        if (tempMarker) {
            map.removeLayer(tempMarker);
        }
        if (tempCircle) {
            map.removeLayer(tempCircle);
        }

        // Dodaj tymczasowy marker
        tempMarker = L.marker(latlng).addTo(map)
            .bindPopup("Wybrana lokalizacja<br>Kontynuuj w menu")
            .openPopup();

        // Dodaj tymczasowy okrąg
        tempCircle = L.circle(latlng, {
            radius: 50,
            color: 'red',
            fillColor: '#f03',
            fillOpacity: 0.2
        }).addTo(map);

        // Wyłącz tryb alertu po wybraniu lokalizacji
        alertMode = false;

        // Pokaż potwierdzenie i opcje dalszego działania
        sendAlertToBackend(latlng);
    });

    // --- WYSYŁANIE DO BACKENDU - CZĘŚĆ 2: FINALIZACJA ---
    function sendAlertToBackend(latlng) {
        alert(latlng)
        // Zamień tymczasowe elementy na stałe
        if (tempMarker) {
            // Możesz zmienić styl markera na stały
            tempMarker.setIcon(L.icon({
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowSize: [41, 41]
            }));
            tempMarker.bindPopup("Alert - niebezpieczeństwo").openPopup();
            tempMarker = null; // Nie usuwaj, tylko przestań śledzić
        }

    if (tempCircle) {
        tempCircle.setStyle({
            color: 'red',
            fillColor: '#f03',
            fillOpacity: 0.3,
            weight: 2
        });
        tempCircle = null;
    }

    selectedLocation = null;
}

// --- PO ZALOGOWANIU ZAŁADUJ ALERTY ---
document.addEventListener('DOMContentLoaded', function() {
    loadAllAlerts();
});

// Pozostały kod bez zmian...
function toggleMenu() {
    document.getElementById('menu').classList.toggle('open');
}

function enableAlertMode() {
    var userEmail = '{{ user_email }}';
    if (!userEmail) {
        alert("Musisz być zalogowany, aby dodać alert.");
        return;
    }

    alertMode = true;
    selectedLocation = null;

    if (tempMarker) {
        map.removeLayer(tempMarker);
        tempMarker = null;
    }
    if (tempCircle) {
        map.removeLayer(tempCircle);
        tempCircle = null;
    }

    toggleMenu();
}

map.on('click', function(e) {
    if (!alertMode) return;

    var latlng = e.latlng;
    selectedLocation = latlng;

    if (tempMarker) {
        map.removeLayer(tempMarker);
    }
    if (tempCircle) {
        map.removeLayer(tempCircle);
    }

    tempMarker = L.marker(latlng).addTo(map)
        .bindPopup("Wybrana lokalizacja")
        .openPopup();

    tempCircle = L.circle(latlng, {
        radius: 50,
        color: 'red',
        fillColor: '#f03',
        fillOpacity: 0.2
    }).addTo(map);

    alertMode = false;
    sendAlertToBackend(latlng);
});