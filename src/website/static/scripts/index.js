var map = L.map('map').setView([50.0647, 19.9450], 13);
var alertMode = false;
var selectedLocation = null;
var tempMarker = null;
var tempCircle = null;
var heatmapLayer = null;
var userMarkers = [];
var userLocationMarker = null;
var userLocationCircle = null;
var watchID = null;
var userCurrentLatlng = null; // Przechowuje ostatnią znaną pozycję do centrowania

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);


var locationControl = L.control({position: 'bottomright'}); 

locationControl.onAdd = function (map) {
    var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-custom leaflet-control-locate');
    container.innerHTML = '<a href="#" title="Centruj na mojej lokalizacji" role="button" aria-label="Centruj na mojej lokalizacji"><i id="location-btn-icon" class="fa fa-crosshairs"></i></a>';
    
    container.style.backgroundColor = 'white';
    container.style.width = '30px';
    container.style.height = '30px';
    container.style.lineHeight = '30px';
    container.style.textAlign = 'center';
    container.style.cursor = 'pointer';

    L.DomEvent.on(container, 'click', function(e) {
        L.DomEvent.stopPropagation(e);
        centerOnUserLocation(map);
    });

    return container;
};

locationControl.addTo(map);

function startBackgroundTracking() {
    if (!("geolocation" in navigator)) {
        console.error("Geolocation API nie jest wspierane.");
        return;
    }

    var successCallback = function(position) {
        var lat = position.coords.latitude;
        var lng = position.coords.longitude;
        var accuracy = position.coords.accuracy;
        var latlng = L.latLng(lat, lng);
        
        userCurrentLatlng = latlng; 

        var customIcon = L.divIcon({
            className: 'user-location-icon',
            html: '<div style="background-color: #4A89F3; width: 15px; height: 15px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 2px rgba(0,0,0,0.5);"></div>',
            iconSize: [19, 19], 
            iconAnchor: [10, 10]
        });

        if (userLocationMarker === null) {
            userLocationMarker = L.marker(latlng, { icon: customIcon }).addTo(map);
            userLocationCircle = L.circle(latlng, { 
                radius: accuracy, color: '#1a0dab', fillColor: '#1a0dab', fillOpacity: 0.15, weight: 1
            }).addTo(map);
            
            // Wyśrodkuj przy pierwszym udanym starcie
            map.setView(latlng, 16); 
        } else {
            userLocationMarker.setLatLng(latlng);
            userLocationCircle.setLatLng(latlng).setRadius(accuracy);
        }
    };
    
    var errorCallback = function(error) {
        console.warn("Błąd geolokalizacji:", error.message);
    };
    
    watchID = navigator.geolocation.watchPosition(
        successCallback,
        errorCallback,
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
}

function centerOnUserLocation(mapInstance) {
    var btnIcon = document.getElementById('location-btn-icon');
    var btnContainer = btnIcon.parentNode.parentNode;
    
    if (userCurrentLatlng) {
        mapInstance.setView(userCurrentLatlng, 16); 
        
        btnIcon.classList.add('fa-spin');
        btnContainer.style.backgroundColor = '#dff0d8';

        setTimeout(() => {
            btnIcon.classList.remove('fa-spin');
            btnContainer.style.backgroundColor = 'white';
        }, 1500); 

    } else {
        alert("Oczekiwanie na ustalenie lokalizacji. Spróbuj ponownie za chwilę.");
        startBackgroundTracking(); 
    }
}

// =================================================================
// ORYGINALNE FUNKCJE
// =================================================================

function loadAllAlerts() {
    fetch("/api/reports")
        .then(res => {
            if (!res.ok) throw new Error('Network response was not ok');
            return res.json();
        })
        .then(data => {
            userMarkers.forEach(item => {
                map.removeLayer(item.marker);
                map.removeLayer(item.circle);
            });
            userMarkers = [];

            data.forEach(alert => {
                if (alert.x != null && alert.y != null) {
                    var latlng = [alert.x, alert.y];

                    var marker = L.marker(latlng).addTo(map)
                        .bindPopup(`
                            <b>${alert.label || 'Alert'}</b><br>
                            Data: ${alert.date}<br>
                            ${alert.email ? `Użytkownik: ${alert.email}` : ''}
                        `);

                    var circle = L.circle(latlng, {
                        radius: 50,
                        color: 'red',
                        fillColor: '#f03',
                        fillOpacity: 0.2
                    }).addTo(map);

                    userMarkers.push({
                        marker: marker, circle: circle, id: alert.id
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
    const t = (normalized - 0.75) * 4;

    if (normalized < 0.25) {
        var alpha = normalized * 4;
        return `rgba(255, 255, 0, ${alpha * 0.8})`;
    } else if (normalized < 0.5) {
        return `rgba(255, ${255 - t * 128}, 0, ${0.7 + t * 0.3})`;
    } else if (normalized < 0.75) {
        return `rgba(255, ${127 - t * 127}, 0, ${0.9})`;
    } else {
        return `rgba(${255 - t * 55}, 0, 0, 1)`;
    }
}

function drawHeatmapCanvas(heatmapData, bounds) {
    var canvas = document.createElement('canvas');
    var resolution = heatmapData.grid_info.resolution;
    canvas.width = resolution;
    canvas.height = resolution;

    var ctx = canvas.getContext('2d');
    var grid = heatmapData.heatmap;

    var flatGrid = grid.flat();
    var maxValue = Math.max(...flatGrid);
    var minValue = Math.min(...flatGrid.filter(v => v > 0));

    if (minValue === undefined || minValue === Infinity) {
        minValue = 0;
    }

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

function loadHeatmap() {
    fetch('/api/heatmap')
        .then(res => res.json())
        .then(response => {
            if (response.status !== 'ok') {
                console.error('Failed to load heatmap:', response.message);
                return;
            }

            var data = response.data;
            var bounds = data.bounds;

            var canvas = drawHeatmapCanvas(data, bounds);

            if (heatmapLayer) {
                map.removeLayer(heatmapLayer);
            }

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

            if (heatmapLayer.getElement()) {
                heatmapLayer.getElement().style.zIndex = 400;
            }

            console.log('Heatmap loaded successfully');
        })
        .catch(error => {
            console.error('Error loading heatmap:', error);
        });
}

function toggleMenu() {
    document.getElementById('menu').classList.toggle('open');
}

function closeMenuAndReturnToMap() {
    document.getElementById('menu').classList.remove('open');
    map.getContainer().focus();
}

function enableAlertMode() {
    if (!'{{user_email}}') {
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

function sendAlertToBackend(latlng) {
    var userEmail = '{{ user_email }}';
    if (!userEmail) {
        alert("Musisz być zalogowany, aby dodać alert.");
        return;
    }

    fetch("/api/reports", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            lat: latlng.lat,
            lng: latlng.lng
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.status === "success") {
            loadAllAlerts();
        } else {
            alert("Błąd podczas dodawania alertu: " + data.message);
        }
    })
    .catch(error => {
        console.error("Error:", error);
        alert("Błąd połączenia z serwerem.");
    });

    if (tempMarker) {
        tempMarker.setIcon(L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        }));
        tempMarker.bindPopup("Alert - niebezpieczeństwo").openPopup();
        tempMarker = null;
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

document.addEventListener('DOMContentLoaded', function() {
    loadAllAlerts();
    loadHeatmap();
    // Rozpocznij śledzenie w tle
    startBackgroundTracking(); 
});