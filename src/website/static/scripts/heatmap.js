function getHeatColor(value, min, max) {
    var normalized = (value - min) / (max - min);
    const t = (normalized - 0.75) * 4;

    if (normalized < 0.25) {
        var alpha = normalized * 8;
        return `rgba(200, 150, 255, ${alpha * 0.8})`; // light purple
    } else if (normalized < 0.5) {
        return `rgba(180, ${150 - t * 50}, 255, ${0.7 + t * 0.3})`; // medium purple
    } else if (normalized < 0.75) {
        return `rgba(150, ${100 - t * 50}, 255, 0.9)`; // darker purple
    } else {
        return `rgba(${120 - t * 40}, 0, 180, 1)`; // deep violet
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