    var map = L.map('map').setView([50.0647, 19.9450], 13);
    var alertMode = false;
    var selectedLocation = null; // Przechowuje wybrane współrzędne
    var tempMarker = null; // Tymczasowy marker
    var tempCircle = null; // Tymczasowy okrąg


    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
    }).addTo(map);

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
      alert('{{user_email}}')
        if (!'{{user_email}}') {
            alert("Musisz być zalogowany, aby dodać alert.");
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
        alert("Kliknij na mapie, aby wybrać lokalizację alertu.");
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
        showAlertConfirmation(latlng);
    });

    // --- CZĘŚĆ 2: POTWIERDZENIE I WYSYŁANIE ---
    function showAlertConfirmation(latlng) {
        var confirmation = confirm(
            "Wybrano lokalizację:\n" +
            "Szerokość: " + latlng.lat.toFixed(6) + "\n" +
            "Długość: " + latlng.lng.toFixed(6) + "\n\n" +
            "Czy chcesz wysłać alert dla tej lokalizacji?"
        );

        if (confirmation) {
            sendAlertToBackend(latlng);
        } else {
            // Użytkownik anulował - usuń tymczasowe elementy
            if (tempMarker) {
                map.removeLayer(tempMarker);
                tempMarker = null;
            }
            if (tempCircle) {
                map.removeLayer(tempCircle);
                tempCircle = null;
            }
            selectedLocation = null;
            alert("Anulowano dodawanie alertu.");
        }
    }

    // --- WYSYŁANIE DO BACKENDU - CZĘŚĆ 2: FINALIZACJA ---
    function sendAlertToBackend(latlng) {
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
            // Zmień styl okręgu na stały
            tempCircle.setStyle({
                color: 'red',
                fillColor: '#f03',
                fillOpacity: 0.3,
                weight: 2
            });
            tempCircle = null; // Nie usuwaj, tylko przestań śledzić
        }

        // Wyślij do backendu
        fetch("/api/reports", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                lat: latlng.lat,
                lng: latlng.lng,
                timestamp: new Date().toISOString()
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === "ok") {
                alert("Alert został pomyślnie dodany!");
            } else {
                alert("Błąd podczas dodawania alertu: " + data.message);
            }
        })
        .catch(error => {
            console.error("Error:", error);
            alert("Błąd połączenia z serwerem.");
        });

        selectedLocation = null;
    }

    // --- DODATKOWE FUNKCJE DO WYKORZYSTANIA WSPÓŁRZĘDNYCH ---

    // Funkcja do pobrania wybranych współrzędnych (dla innych funkcji)
    function getSelectedLocation() {
        return selectedLocation;
    }

    // Funkcja do wyświetlenia szczegółów lokalizacji w menu
    function showLocationDetails() {
        if (!selectedLocation) {
            alert("Najpierw wybierz lokalizację na mapie!");
            return;
        }

        var details = `
            Wybrana lokalizacja:
            Szerokość: ${selectedLocation.lat.toFixed(6)}
            Długość: ${selectedLocation.lng.toFixed(6)}

            Co chcesz zrobić?
        `;

        var action = prompt(details + "\n1 - Wyślij alert\n2 - Pobierz współrzędne\n3 - Anuluj");

        switch(action) {
            case "1":
                sendAlertToBackend(selectedLocation);
                break;
            case "2":
                navigator.clipboard.writeText(`${selectedLocation.lat}, ${selectedLocation.lng}`);
                alert("Współrzędne skopiowane do schowka!");
                break;
            case "3":
                // Anuluj - usuń tymczasowe elementy
                if (tempMarker) map.removeLayer(tempMarker);
                if (tempCircle) map.removeLayer(tempCircle);
                tempMarker = null;
                tempCircle = null;
                selectedLocation = null;
                break;
        }
    }

    // --- Pobranie istniejących alertów ---
    fetch("/api/reports")
        .then(res => res.json())
        .then(data => {
            data.forEach(r => {
                var latlng = [r.lat, r.lng];
                var marker = L.marker(latlng).addTo(map)
                    .bindPopup("Alert - niebezpieczeństwo");

                L.circle(latlng, {
                    radius: 50,
                    color: 'red',
                    fillColor: '#f03',
                    fillOpacity: 0.2
                }).addTo(map);
            });
        });

    // Zamknij menu gdy klikniesz poza nim
    document.addEventListener('click', function(event) {
        var menu = document.getElementById('menu');
        var menuBtn = document.querySelector('.menu-btn');
        if (!menu.contains(event.target) && !menuBtn.contains(event.target) && menu.classList.contains('open')) {
            toggleMenu();
        }
    });