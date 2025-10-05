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