import numpy as np
import matplotlib.pyplot as plt
from src.database.db import view_all
import math
from pyproj import Transformer

transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

def convert_point(x, y):
    """Konwertuje współrzędne z EPSG:2180 na (lat, lon) w EPSG:4326."""
    # pyproj returns (lon, lat) when always_xy=True, we swap to (lat, lon)
    lon, lat = transformer.transform(x, y)
    return lat, lon

# Zmieniona sygnatura: używamy radius_degrees zamiast radius_meters
def create_heatmap(resolution=100, radius_degrees=0.01, normalize=True):
    # Uwaga: 0.005 stopnia to mniej więcej 550 metrów

    # 1. Pobranie i przygotowanie danych
    data = view_all()
    if not data:
        return None, None, None

    points = []
    for row in data:
        if row['coordinates'] and row['trust'] is not None:
            lat, lon = row['coordinates']
            points.append({'lat': lat, 'lon': lon, 'trust': row['trust']})

    if not points:
        return None, None, None

    lats = [p['lat'] for p in points]
    lons = [p['lon'] for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    lat_padding = 0.001
    lon_padding = 0.001
    min_lat -= lat_padding
    max_lat += lat_padding
    min_lon -= lon_padding
    max_lon += lon_padding

    bounds = {
        'min_lat': min_lat, 'max_lat': max_lat,
        'min_lon': min_lon, 'max_lon': max_lon
    }

    trust_values = [p['trust'] for p in points]
    if normalize and trust_values:
        min_trust = min(trust_values)
        max_trust = max(trust_values)
        trust_range = max_trust - min_trust if max_trust != min_trust else 1
        for p in points:
            p['trust_scaled'] = (p['trust'] - min_trust) / trust_range
    else:
        for p in points:
            p['trust_scaled'] = p['trust']

    heatmap = np.zeros((resolution, resolution))
    lat_step = (max_lat - min_lat) / resolution
    lon_step = (max_lon - min_lon) / resolution

    delta_i = math.ceil(radius_degrees / lat_step)
    delta_j = math.ceil(radius_degrees / lon_step)

    for point in points:

        i_center = int((point['lat'] - min_lat) / lat_step)
        j_center = int((point['lon'] - min_lon) / lon_step)

        i_min = max(0, i_center - delta_i)
        i_max = min(resolution, i_center + delta_i + 1)
        j_min = max(0, j_center - delta_j)
        j_max = min(resolution, j_center + delta_j + 1)

        for i in range(i_min, i_max):
            for j in range(j_min, j_max):
                # Środek komórki siatki
                grid_lat = min_lat + (i + 0.5) * lat_step
                grid_lon = min_lon + (j + 0.5) * lon_step

                distance_degrees = math.sqrt((point["lat"] - grid_lat) ** 2 + (point["lon"] - grid_lon) ** 2)

                # Poprawny warunek zasięgu (stopnie vs. stopnie)
                if distance_degrees <= radius_degrees:
                    # Funkcja jądra (prosty kernel: stała wartość w promieniu)
                    heatmap[i, j] += abs(point['trust_scaled']) * 10

    grid_info = {
        'resolution': resolution,
        'radius_degrees': radius_degrees,  # Nowa jednostka zasięgu
        'lat_step': lat_step,
        'lon_step': lon_step,
        'num_points': len(points),
        'normalized': normalize,
        'delta_i': delta_i,
        'delta_j': delta_j
    }
    bounds['min_lat'], bounds['min_lon'] = convert_point(min_lat, min_lon)
    bounds['max_lat'], bounds['max_lon'] = convert_point(max_lat, max_lon)

    return heatmap, bounds, grid_info



def print_heatmap_stats(heatmap, bounds, grid_info):
    """Print statistics about the generated heatmap."""
    if heatmap is None:
        print("No heatmap data available.")
        return

    print("=" * 50)
    print("HEATMAP STATISTICS (Euklidesowa Metryka)")
    print("=" * 50)
    print(f"Grid resolution: {grid_info['resolution']}x{grid_info['resolution']}")
    print(f"Radius (Degrees): {grid_info['radius_degrees']:.6f}") 
    print(f"Number of points: {grid_info['num_points']}")
    print(f"Normalized: {grid_info['normalized']}")
    print(f"Optimization range (cells): +/- {grid_info['delta_i']} (lat), +/- {grid_info['delta_j']} (lon)")
    print(f"\nBounds:")
    print(f"  Latitude: {bounds['min_lat']:.6f} to {bounds['max_lat']:.6f}")
    print(f"  Longitude: {bounds['min_lon']:.6f} to {bounds['max_lon']:.6f}")
    print(f"\nHeat values:")
    print(f"  Min: {heatmap.min():.4f}")
    print(f"  Max: {heatmap.max():.4f}")
    print(f"  Mean: {heatmap.mean():.4f}")
    print(f"  Non-zero cells: {np.count_nonzero(heatmap)}")
    print("=" * 50)


def plot_heatmap(heatmap, bounds, grid_info, title="Trust Heatmap",
                 cmap='hot', figsize=(12, 10), show_points=True, save_path=None):
    if heatmap is None:
        print("No heatmap data available to plot.")
        return

    fig, ax = plt.subplots(figsize=figsize)

    extent = [
        bounds['min_lon'], bounds['max_lon'],
        bounds['min_lat'], bounds['max_lat']
    ]

    im = ax.imshow(
        heatmap,
        extent=extent,
        origin='lower',
        cmap=cmap,
        aspect='auto',
        interpolation='bilinear'
    )

    plt.colorbar(im, ax=ax, label='Heat Intensity (Trust Value)')

    if show_points:
        data = view_all() 
        points = [row for row in data if row['coordinates'] and row['trust'] is not None]
        if points:
            lats = [p['coordinates'][0] for p in points]
            lons = [p['coordinates'][1] for p in points]

            ax.scatter(
                lons, lats,
                c='cyan',
                s=50,
                marker='o',
                edgecolors='white',
                linewidths=1.5,
                alpha=0.8,
                label='Original Points',
                zorder=5
            )
            ax.legend(loc='upper right')

    ax.set_xlabel('Longitude', fontsize=12)
    ax.set_ylabel('Latitude', fontsize=12)
    radius_str = f'Radius: {grid_info["radius_degrees"]:.4f}°'
    ax.set_title(
        f'{title} (Uproszczona Metryka)\n({radius_str}, Points: {grid_info["num_points"]}, Resolution: {grid_info["resolution"]}x{grid_info["resolution"]})',
        fontsize=14,
        pad=20
    )

    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path)
    
    plt.show()

if __name__ == '__main__':
    heatmap, bounds, grid_info = create_heatmap(radius_degrees=500.0, resolution=100)
    plot_heatmap(heatmap, bounds, grid_info)