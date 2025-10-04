import numpy as np
import matplotlib.pyplot as plt
from src.database.db import view_all
import math
from pyproj import Transformer

transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

def convert_point(x, y):
    # pyproj returns (lon, lat) when always_xy=True
    lon, lat = transformer.transform(x, y)
    return lat, lon

def create_heatmap(resolution=100, radius_meters=500.0, normalize=True):

    # Get all data from database
    data = view_all()

    if not data:
        return None, None, None

    # Extract coordinates and trust values
    points = []
    for row in data:
        if row['coordinates'] and row['trust'] is not None:
            lat, lon = row['coordinates']
            points.append({
                'lat': lat,
                'lon': lon,
                'trust': row['trust']
            })

    if not points:
        return None, None, None

    # Find bounds
    lats = [p['lat'] for p in points]
    lons = [p['lon'] for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Add padding to bounds (about 100 meters in degrees, roughly)
    # At mid-latitudes, 1 degree ≈ 111km, so 100m ≈ 0.0009 degrees
    lat_padding = 0.001
    lon_padding = 0.001
    min_lat -= lat_padding
    max_lat += lat_padding
    min_lon -= lon_padding
    max_lon += lon_padding

    bounds = {
        'min_lat': min_lat,
        'max_lat': max_lat,
        'min_lon': min_lon,
        'max_lon': max_lon
    }

    # Normalize trust values if requested
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

    # Create grid
    heatmap = np.zeros((resolution, resolution))

    # Generate grid coordinates
    lat_step = (max_lat - min_lat) / resolution
    lon_step = (max_lon - min_lon) / resolution

    # For each point, find all grid cells within radius and add trust value
    for point in points:
        for i in range(resolution):
            for j in range(resolution):
                # Grid cell center coordinates
                grid_lat = min_lat + (i + 0.5) * lat_step
                grid_lon = min_lon + (j + 0.5) * lon_step

                # Calculate distance from point to grid cell
                # distance = haversine_distance(
                #     point['lat'], point['lon'],
                #     grid_lat, grid_lon
                # )
                distance = math.sqrt((point["lat"] - grid_lat)**2 + (point["lon"] - grid_lon)**2)

                # If grid cell is within radius, add scaled trust value
                if distance/4 <= radius_meters:
                    heatmap[i, j] += point['trust_scaled']*10

    grid_info = {
        'resolution': resolution,
        'radius_meters': radius_meters,
        'lat_step': lat_step,
        'lon_step': lon_step,
        'num_points': len(points),
        'normalized': normalize
    }
    bounds["min_lat"], bounds['min_lon'] = convert_point(min_lat, min_lon)
    bounds["max_lat"], bounds['max_lon'] = convert_point(max_lat, max_lon)

    return heatmap, bounds, grid_info


def print_heatmap_stats(heatmap, bounds, grid_info):
    """Print statistics about the generated heatmap."""
    if heatmap is None:
        print("No heatmap data available.")
        return

    print("=" * 50)
    print("HEATMAP STATISTICS")
    print("=" * 50)
    print(f"Grid resolution: {grid_info['resolution']}x{grid_info['resolution']}")
    print(f"Radius: {grid_info['radius_meters']} meters")
    print(f"Number of points: {grid_info['num_points']}")
    print(f"Normalized: {grid_info['normalized']}")
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

    # Create extent for proper geographic coordinate display
    extent = [
        bounds['min_lon'], bounds['max_lon'],
        bounds['min_lat'], bounds['max_lat']
    ]

    # Plot heatmap
    im = ax.imshow(
        heatmap,
        extent=extent,
        origin='lower',
        cmap=cmap,
        aspect='auto',
        interpolation='bilinear'
    )

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Heat Intensity (Trust Value)')

    # Overlay original points if requested
    if show_points:
        data = view_all()
        points = [row for row in data if row['coordinates'] and row['trust'] is not None]
        if points:
            lats = [p['coordinates'][0] for p in points]
            lons = [p['coordinates'][1] for p in points]
            trusts = [p['trust'] for p in points]

            scatter = ax.scatter(
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

    # Labels and title
    ax.set_xlabel('Longitude', fontsize=12)
    ax.set_ylabel('Latitude', fontsize=12)
    ax.set_title(
        f'{title}\n(Radius: {grid_info["radius_meters"]}m, '
        f'Points: {grid_info["num_points"]}, '
        f'Resolution: {grid_info["resolution"]}x{grid_info["resolution"]})',
        fontsize=14,
        pad=20
    )

    # Add grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

    plt.tight_layout()

    plt.show()


# Example usage
if __name__ == '__main__':
    # Generate heatmap with default settings
    heatmap, bounds, grid_info = create_heatmap(
        resolution=100,
        radius_meters=100.0,
        normalize=True
    )

    if heatmap is not None:
        print_heatmap_stats(heatmap, bounds, grid_info)

        # Visualize the heatmap
        plot_heatmap(
            heatmap,
            bounds,
            grid_info,
            title="Trust Heatmap",
            cmap='hot',  # Try 'YlOrRd', 'plasma', 'viridis', 'coolwarm'
            show_points=True,
            save_path='heatmap_visualization.png'  # Set to None to display instead
        )

        # You can save the heatmap data to a file
        np.save('heatmap_data.npy', heatmap)
        print("\nHeatmap data saved to 'heatmap_data.npy'")

        # Example: Get heat value at a specific grid position
        print(f"\nSample heat value at grid[50, 50]: {heatmap[50, 50]:.4f}")
    else:
        print("No data available to generate heatmap.")