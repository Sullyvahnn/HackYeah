// index.js - POPRAWIONE ŁADOWANIE ALERTÓW

var map = L.map('map').setView([50.0647, 19.9450], 13);
var alertMode = false;
var selectedLocation = null;
var tempMarker = null;
var tempCircle = null;
var userMarkers = [];

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);

// --- FUNKCJA DO ŁADOWANIA ALERTÓW ---
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

// --- WYSYŁANIE ALERTU DO BACKENDU ---
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
            loadAllAlerts(); // Przeładuj alerty
        } else {
            alert("Błąd podczas dodawania alertu: " + data.message);
        }
    })
    .catch(error => {
        console.error("Error:", error);
        alert("Błąd połączenia z serwerem.");
    });

    // Zamień tymczasowe elementy na stałe
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