# db.py
import os
import sqlite3
import json
from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Email

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Wyślij link logowania')

def connect_db():
    """Connects to the SQLite database and creates the table if it doesn’t exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
    cursor.execute("""
                CREATE TABLE IF NOT EXISTS tokens
                (
                    token
                    TEXT
                    PRIMARY
                    KEY,
                    email
                    TEXT,
                    created_at
                    INTEGER,
                    used
                    INTEGER
                    DEFAULT
                    0
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


# FUNKCJE DLA ALERTÓW UŻYTKOWNIKA

def add_user_alert(email: str, lat: float, lng: float, label: str = "Alert użytkownika"):
    """Dodaje alert użytkownika do bazy danych."""
    conn = connect_db()
    cursor = conn.cursor()

    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    coordinates = json.dumps([lat, lng])

    try:
        # Najpierw upewnij się, że użytkownik istnieje
        cursor.execute("INSERT OR IGNORE INTO User (email) VALUES (?)", (email,))

        # Dodaj alert do scrapped_data z powiązaniem z użytkownikiem
        cursor.execute("""
                       INSERT INTO scrapped_data (date, label, address, city, coordinates, trust, user_email)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       """, (date, label, "", "", coordinates, 100, email))

        conn.commit()
        print(f"Alert użytkownika {email} dodany pomyślnie.")
        return True
    except Exception as e:
        print(f"Błąd podczas dodawania alertu: {e}")
        return False
    finally:
        conn.close()


def get_user_alerts(email: str):
    """Pobiera wszystkie alerty danego użytkownika."""
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
                   SELECT *
                   FROM scrapped_data
                   WHERE user_email = ?
                   ORDER BY date DESC
                   """, (email,))

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
            "user_email": row[7] if len(row) > 7 else None
        }
        result.append(row_dict)
    return result


def get_all_alerts():
    """Pobiera wszystkie alerty wszystkich użytkowników."""
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Coordinate WHERE email IS NOT NULL ORDER BY date DESC")
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
            "user_email": row[7] if len(row) > 7 else None
        }
        result.append(row_dict)
    return result


# FUNKCJE DLA UŻYTKOWNIKÓW

def add_user(email: str):
    """Dodaje nowego użytkownika do tabeli User."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO User (email) VALUES (?)", (email,))
        conn.commit()
        print(f"Użytkownik {email} dodany pomyślnie.")
        return True
    except sqlite3.IntegrityError:
        print(f"Użytkownik z emailem {email} już istnieje.")
        return False
    finally:
        conn.close()


def get_user_by_email(email: str):
    """Pobiera użytkownika po emailu."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM User WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


if __name__ == '__main__':
    conn = connect_db()



