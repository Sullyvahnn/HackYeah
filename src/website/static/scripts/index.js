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
    
    // DODAJ TO - sprawdzanie zagrożenia
    if (typeof checkDangerAtLocation === 'function') {
        checkDangerAtLocation(lat, lng);
    }
    
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



function toggleMenu() {
    document.getElementById('menu').classList.toggle('open');
}

map.on('click', function(e) {

    var latlng = e.latlng;
    selectedLocation = latlng;

    if (tempMarker) {
        map.removeLayer(tempMarker);
    }
    if (tempCircle) {
        map.removeLayer(tempCircle);
    }

    alertMode = false;
    sendAlertToBackend(latlng);
});

document.addEventListener('DOMContentLoaded', function() {
    loadAllAlerts();
    loadHeatmap();
    // Rozpocznij śledzenie w tle
    startBackgroundTracking();
    fetch('/api/heatmap').then(r => r.json()).then(console.log);
});