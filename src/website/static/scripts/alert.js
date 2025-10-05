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
    if (!latlng || latlng.lat == null || latlng.lng == null) {
        console.error("Invalid coordinates");
        return;
    }

    fetch("/api/reports", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            date: new Date().toISOString(),
            coordinates: [latlng.lat, latlng.lng]
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
            loadAllAlerts();   // refresh alerts
            loadHeatmap();     // refresh heatmap
        } else {
            alert("Błąd podczas dodawania alertu: " + data.message);
        }
    })
    .catch(error => {
        console.error("Error:", error);
    });
}
