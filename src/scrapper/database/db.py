# db.py
import sqlite3
import json
from datetime import datetime

DB_NAME = "scrapped.db"

def connect_db():
    """Connects to the SQLite database and creates the table if it doesn’t exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrapped_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,          -- Stored as ISO date string (YYYY-MM-DD)
            label TEXT NOT NULL,
            address TEXT,
            city TEXT,
            coordinates TEXT,            -- JSON array of two floats
            trust INTEGER
        )
    """)
    conn.commit()
    return conn

def add_row(date = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            label: str = None,
            address: str = None,
            city: str = None,
            coordinates: list[float] = None,
            trust: int = None):
    """
    Adds a new row to the database.
    - label: keyword label
    - address: string
    - city: string
    - coordinates: [latitude, longitude] as list of floats
    - trust: integer
    """
    if not (isinstance(coordinates, list) and len(coordinates) == 2 and all(isinstance(c, float) for c in coordinates)):
        raise ValueError("coordinates must be a list of two floats: [latitude, longitude]")

    conn = connect_db()
    cursor = conn.cursor()

    coord_json = json.dumps(coordinates)

    cursor.execute("""
        INSERT INTO scrapped_data (date, label, address, city, coordinates, trust)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (date, label, address, city, coord_json, trust))

    conn.commit()
    conn.close()
    print("Row added successfully.")

def delete_row(row_id: int):
    """Deletes a row from the database by ID."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scrapped_data WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
    print(f"🗑Row with ID {row_id} deleted (if it existed).")

def view_all():
    """Returns all rows in the database, decoding coordinates to Python lists."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scrapped_data")
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        row_dict = {
            "id": row[0],
            "date": row[1],
            "label": row[2],
            "address": row[3],
            "city": row[4],
            "coordinates": json.loads(row[5]) if row[5] else None,
            "trust": row[6],
        }
        result.append(row_dict)
    return result


def row_exists(date, label=None, coordinates=None):
    """Check if a row with the same date, label, and coordinates already exists."""
    conn = connect_db()
    cursor = conn.cursor()

    x, y = (coordinates if coordinates else (None, None))

    cursor.execute('''
                   SELECT 1
                   FROM scrapped_data
                   WHERE date = ?
                     AND label = ?
                     AND coordinates = ?
                       LIMIT 1
                   ''', (date, label, json.dumps(coordinates)))

    exists = cursor.fetchone() is not None
    conn.close()
    return exists


