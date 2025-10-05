import requests
from time import sleep
from src.database.db import add_row, row_exists
from datetime import datetime

# ----------CONFIG--------------
base_url = "https://mapy.geoportal.gov.pl/iMapLite/imlDataService/service/data/clust/get"
map_id = "4028e4e54e6ceb84014e6ced4d1c0000"
layer_id = "4028e4e54e6ceb84014e6ced4d230001"

# Raw filter (unencoded)
filter_raw = '''(
    'Typ'="Akty wandalizmu",
    "Grupowanie się małoletnich zagrożonych demoralizacją",
    "Miejsce niebezpiecznej działalności rozrywkowej",
    "Nielegalne rajdy samochodowe",
    "Spożywanie alkoholu w miejscach niedozwolonych",
    "Używanie środków odurzających",
    "Wałęsające się bezpańskie psy",
    "Żebractwo"
)
AND 
(
    (
        ('Typ'!="Miejsce niebezpiecznej działalności rozrywkowej",
        "Znęcanie się nad zwierzętami",
        "Używanie środków odurzających")
        AND
        (
            ('Status'="Nowe","Weryfikacja","Potwierdzone", "Potwierdzone (przekazane poza Policję)")
            OR
            (('Status'="Niepotwierdzone") AND ('Data modyfikacji'>=1758924000000))
            OR
            (('Status'="Potwierdzone (wyeliminowane)") AND ('Data modyfikacji'>=1756936800000))
        )
    )
    OR
    (
        ('Typ'="Miejsce niebezpiecznej działalności rozrywkowej")
        AND
        (
            ('Status'="Potwierdzone")
            OR ('Status'="Potwierdzone (przekazane poza Policję)")
            OR (('Status'="Potwierdzone (wyeliminowane)") AND ('Data modyfikacji'>=1756936800000))
        )
    )
)'''

TRUST_WERYFIKACJA = -1
TRUST_POTWIERDZONE_WYELIMINOWANE = 1
TRUST_POTWIERDZONE = 2
TRUST_NIEPOTWIERDZONE = 2
TRUST_POTWIERDZONE_PRZEKAZANE_POZA_POLICJE = 0
TRUST_OTHER = 3


# Poland bounds in EPSG:2180
xmin, xmax = 560000, 578000
ymin, ymax = 238000, 251000
tile_size = 378

# ----------CONFIG--------------

def scrap():
    # Create a custom session that doesn't encode parentheses
    session = requests.Session()

    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            bbox = f"{x},{y},{x + tile_size},{y + tile_size}"

            # Build URL manually with custom encoding
            from urllib.parse import quote

            encoded_filter = quote(filter_raw, safe="()='!,")

            full_url = f"{base_url}/{map_id}/{layer_id}?bbox={bbox}&s=-1&filtr={encoded_filter}"

            try:
                r = session.get(full_url, timeout=10)
                print(f"Status: {r.url}")

                if r.status_code == 200:
                    data = r.json()
                    if "features" in data:
                        insert_crime_data(data)
                        print(f"  → Found {len(data['features'])} features")
                    else:
                        print(f"  → No features in response")
                else:
                    print(f"  → Error response: {r.text[:200]}")

            except requests.exceptions.Timeout:
                print(f"  → Timeout")
            except Exception as e:
                print(f"  → Error: {e}")

            y += tile_size
            sleep(0.2)
        x += tile_size


def millis_to_date(ms):
    """Converts Unix time in milliseconds to a human-readable date string.
       Returns None if timestamp is missing or older than year 2000."""
    if ms is None:
        return None  # No timestamp given

    try:
        date = datetime.fromtimestamp(ms / 1000)
    except Exception:
        return None

    # Skip dates older than year 2000
    if date.year < 2000:
        return None

    return date.strftime('%Y-%m-%d %H:%M:%S')

# Function to get trust value from status
def get_trust(status):
    mapping = {
        "Weryfikacja": TRUST_WERYFIKACJA,
        "Potwierdzone (wyeliminowane)": TRUST_POTWIERDZONE_WYELIMINOWANE,
        "Potwierdzone": TRUST_POTWIERDZONE,
        "Niepotwierdzone": TRUST_NIEPOTWIERDZONE,
        "Potwierdzone (przekazane poza Policję)": TRUST_POTWIERDZONE_PRZEKAZANE_POZA_POLICJE
    }
    return mapping.get(status, TRUST_OTHER)


# Function to insert data using db.add_row
def insert_crime_data(data):
    for feature in data['features']:
        attr = feature['attributes']
        date = millis_to_date(attr['Data zdarzenia'])
        if date is None:
            continue
        label = attr['Typ']
        coordinates = [feature['geometry']['x'], feature['geometry']['y']]
        trust = get_trust(attr['Status'])
        print(date, label, coordinates, trust)

        if not row_exists(date=date, label=label, coordinates=coordinates):
            add_row(
                date=date,
                label=label,
                coordinates=coordinates,
                trust=trust,
                user=None
            )
        else:
            print(f"Crime already exists: {date}, {label}, {coordinates}")

if __name__ == "__main__":
    scrap()
    # Save as single GeoJSON
    # geojson = {"type": "FeatureCollection", "features": all_features}
    # with open("kmzb_all.geojson", "w", encoding="utf-8") as f:
    #     json.dump(geojson, f, ensure_ascii=False, indent=2)