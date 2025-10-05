function getHeatColor(value, min, max) {
    var normalized = (value - min) / (max - min);
    
    // Bardziej różnorodna paleta kolorów
    if (normalized < 0.15) {
        // Bardzo niskie - niebieski/cyjan
        var alpha = normalized / 0.15;
        return `rgba(0, ${Math.floor(150 * alpha)}, ${Math.floor(255 * alpha)}, ${alpha * 0.6})`;
    } else if (normalized < 0.35) {
        // Niskie - zielony/turkusowy
        var t = (normalized - 0.15) / 0.2;
        return `rgba(0, ${Math.floor(200 - t * 50)}, ${Math.floor(200 - t * 100)}, ${0.6 + t * 0.1})`;
    } else if (normalized < 0.55) {
        // Średnie - żółty/zielony
        var t = (normalized - 0.35) / 0.2;
        return `rgba(${Math.floor(t * 200)}, ${Math.floor(220 - t * 20)}, ${Math.floor(100 - t * 100)}, ${0.7 + t * 0.1})`;
    } else if (normalized < 0.75) {
        // Wysokie - pomarańczowy
        var t = (normalized - 0.55) / 0.2;
        return `rgba(${Math.floor(255)}, ${Math.floor(180 - t * 80)}, 0, ${0.8 + t * 0.1})`;
    } else {
        // Bardzo wysokie - czerwony/ciemnoczerwony
        var t = (normalized - 0.75) / 0.25;
        return `rgba(${Math.floor(255 - t * 55)}, ${Math.floor(50 - t * 50)}, 0, ${0.9 + t * 0.1})`;
    }
}

function drawHeatmapCanvas(heatmapData, bounds) {
    var canvas = document.createElement('canvas');
    var resolution = heatmapData.grid_info.resolution;
    
    // Zwiększ rozmiar canvas dla lepszej jakości
    var scale = 2;
    canvas.width = resolution * scale;
    canvas.height = resolution * scale;
    
    var ctx = canvas.getContext('2d');
    
    // Włącz antyaliasing i gładkie renderowanie
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    
    var grid = heatmapData.heatmap;
    
    // Flatten grid and find min/max
    var flatGrid = grid.flat();
    var maxValue = Math.max(...flatGrid);
    var minValue = Math.min(...flatGrid.filter(v => v > 0));
    
    if (minValue === undefined || minValue === Infinity) {
        minValue = 0;
    }
    
    console.log(`Drawing heatmap: resolution=${resolution}, min=${minValue}, max=${maxValue}`);
    
    // Draw each cell z większym rozmiarem
    for (var i = 0; i < resolution; i++) {
        for (var j = 0; j < resolution; j++) {
            var value = grid[i][j];
            if (value > 0) {
                ctx.fillStyle = getHeatColor(value, minValue, maxValue);
                // Rysuj większe prostokąty z lekkim nakładaniem
                ctx.fillRect(
                    j * scale - 0.5, 
                    (resolution - 1 - i) * scale - 0.5, 
                    scale + 1, 
                    scale + 1
                );
            }
        }
    }
    
    return canvas;
}

function loadHeatmap() {
    console.log('Loading heatmap...');
    
    fetch('/api/heatmap')
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
        .then(response => {
            console.log('Heatmap response:', response);
            
            // Obsługa różnych formatów odpowiedzi
            var data;
            
            if (response.status === 'ok' && response.data) {
                // Format: { status: 'ok', data: {...} }
                data = response.data;
            } else if (response.heatmap && response.bounds) {
                // Format: { heatmap: [...], bounds: {...}, grid_info: {...} }
                data = response;
            } else if (response.status === 'error') {
                console.error('Failed to load heatmap:', response.message);
                showNotification('No heatmap data available', 'warning');
                return;
            } else {
                console.error('Unexpected response format:', response);
                showNotification('Invalid heatmap data format', 'error');
                return;
            }
            
            // Walidacja danych
            if (!data.heatmap || !data.bounds || !data.grid_info) {
                console.error('Missing required fields in heatmap data');
                showNotification('Incomplete heatmap data', 'error');
                return;
            }
            
            var bounds = data.bounds;
            var canvas = drawHeatmapCanvas(data, bounds);
            
            // Usuń starą warstwę jeśli istnieje
            if (typeof heatmapLayer !== 'undefined' && heatmapLayer) {
                map.removeLayer(heatmapLayer);
            }
            
            // Dodaj nową warstwę
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
            showNotification('Heatmap loaded', 'success');
        })
        .catch(error => {
            console.error('Error loading heatmap:', error);
            showNotification('Failed to load heatmap', 'error');
        });
}

// Pomocnicza funkcja do wyświetlania powiadomień
function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    // Możesz dodać tutaj prawdziwe powiadomienia UI jeśli masz taki system
}

// Automatyczne odświeżanie heatmapy co 30 sekund (opcjonalnie)
function startHeatmapAutoRefresh(intervalSeconds = 30) {
    loadHeatmap(); // Załaduj od razu
    return setInterval(loadHeatmap, intervalSeconds * 1000);
}

// Eksportuj funkcje jeśli używasz modułów
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        loadHeatmap,
        drawHeatmapCanvas,
        getHeatColor,
        startHeatmapAutoRefresh
    };
}

// =================================================================
// SYSTEM OSTRZEŻEŃ O ZAGROŻENIU
// =================================================================

var lastAlertTime = 0;
var alertCooldown = 30000; // 30 sekund między alertami

// Funkcja sprawdzająca zagrożenie w aktualnej lokalizacji
function checkDangerAtLocation(lat, lon) {
    if (!heatmapLayer) return null;
    
    fetch('/api/heatmap')
        .then(r => r.json())
        .then(response => {
            if (response.status !== 'ok') return;
            
            var data = response.data;
            var bounds = data.bounds;
            var grid = data.heatmap;
            var resolution = data.grid_info.resolution;
            
            // Sprawdź czy użytkownik jest w obszarze heatmapy
            if (lat < bounds.min_lat || lat > bounds.max_lat ||
                lon < bounds.min_lon || lon > bounds.max_lon) {
                return;
            }
            
            // Oblicz indeks w siatce
            var lat_step = (bounds.max_lat - bounds.min_lat) / resolution;
            var lon_step = (bounds.max_lon - bounds.min_lon) / resolution;            
            var i = Math.floor((lat - bounds.min_lat) / lat_step);
            var j = Math.floor((lon - bounds.min_lon) / lon_step);
            
            // Bezpieczeństwo
            if (i < 0 || i >= resolution || j < 0 || j >= resolution) {
                return;
            }
            
            var dangerValue = grid[i][j];
            
            if (dangerValue > 0) {
                showDangerAlert(dangerValue, data);
            }
        })
        .catch(error => {
            console.error('Błąd sprawdzania zagrożenia:', error);
        });
}

// Funkcja wyświetlająca ostrzeżenie
function showDangerAlert(dangerValue, heatmapData) {
    var now = Date.now();
    
    if (now - lastAlertTime < alertCooldown) {
        return;
    }
    lastAlertTime = now;
    
    // Oblicz znormalizowaną wartość
    var flatGrid = heatmapData.heatmap.flat();
    var maxValue = Math.max(...flatGrid);
    var minValue = Math.min(...flatGrid.filter(v => v > 0));
    var normalized = (dangerValue - minValue) / (maxValue - minValue);
    
    var alertLevel, message, color, icon;
    
    if (normalized < 0.25) {
        alertLevel = "NISKIE";
        message = "Znajdujesz się w obszarze o niskim poziomie zagrożenia.";
        color = "#FFA500";
        icon = "⚠️";
    } else if (normalized < 0.5) {
        alertLevel = "ŚREDNIE";
        message = "UWAGA! Znajdujesz się w obszarze o średnim poziomie zagrożenia.";
        color = "#FF6347";
        icon = "⚠️";
    } else if (normalized < 0.75) {
        alertLevel = "WYSOKIE";
        message = "OSTRZEŻENIE! Jesteś w strefie wysokiego zagrożenia. Zachowaj ostrożność!";
        color = "#DC143C";
        icon = "🚨";
    } else {
        alertLevel = "KRYTYCZNE";
        message = "ALARM! Bardzo wysoki poziom zagrożenia w Twojej lokalizacji! Opuść ten obszar!";
        color = "#8B0000";
        icon = "🚨";
    }
    
    // Notyfikacja przeglądarki
    if ("Notification" in window && Notification.permission === "granted") {
        new Notification(`${icon} Zagrożenie: ${alertLevel}`, {
            body: message,
            requireInteraction: true
        });
    }
    
    showInAppAlert(alertLevel, message, color, normalized);
}

// Alert w aplikacji
function showInAppAlert(level, message, color, intensity) {
    var existingAlert = document.getElementById('danger-alert');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    var alertDiv = document.createElement('div');
    alertDiv.id = 'danger-alert';
    alertDiv.style.cssText = `
        position: fixed;
        top: 70px;
        left: 50%;
        transform: translateX(-50%);
        background-color: ${color};
        color: white;
        padding: 15px 30px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        z-index: 10000;
        font-size: 16px;
        font-weight: bold;
        text-align: center;
        animation: slideDown 0.5s ease-out, pulse 2s ease-in-out infinite;
        max-width: 90%;
    `;
    
    alertDiv.innerHTML = `
        <div style="font-size: 20px; margin-bottom: 5px;">ZAGROŻENIE: ${level}</div>
        <div style="font-size: 14px; font-weight: normal;">${message}</div>
        <div style="margin-top: 10px;">
            <div style="background: rgba(255,255,255,0.3); height: 10px; border-radius: 5px; overflow: hidden;">
                <div style="background: white; height: 100%; width: ${intensity * 100}%;"></div>
            </div>
        </div>
        <button onclick="this.parentElement.remove()" style="
            margin-top: 10px;
            background: rgba(255,255,255,0.3);
            border: none;
            color: white;
            padding: 5px 15px;
            border-radius: 5px;
            cursor: pointer;
        ">Zamknij</button>
    `;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        if (alertDiv && alertDiv.parentElement) {
            alertDiv.style.animation = 'slideUp 0.5s ease-out';
            setTimeout(() => alertDiv.remove(), 500);
        }
    }, 10000);
}



// Dodaj style CSS
if (!document.getElementById('danger-alert-styles')) {
    var style = document.createElement('style');
    style.id = 'danger-alert-styles';
    style.textContent = `
        @keyframes slideDown {
            from { top: -100px; opacity: 0; }
            to { top: 70px; opacity: 1; }
        }
        @keyframes slideUp {
            from { top: 70px; opacity: 1; }
            to { top: -100px; opacity: 0; }
        }
        @keyframes pulse {
            0%, 100% { transform: translateX(-50%) scale(1); }
            50% { transform: translateX(-50%) scale(1.02); }
        }
    `;
    document.head.appendChild(style);
}

// Poproś o pozwolenie na notyfikacje
function requestNotificationPermission() {
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();
    }
}

// Wywołaj przy załadowaniu
if (typeof document !== 'undefined') {
    requestNotificationPermission();
}