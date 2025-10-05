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
    """Connects to the SQLite database and creates the tables if they don’t exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS User (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,          -- ISO date string (YYYY-MM-DD)
            label TEXT NOT NULL,
            coordinates TEXT,            -- JSON array of two floats
            trust INTEGER,
            user TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            email TEXT,
            created_at INTEGER,
            used INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    return conn


def add_row(date=None, label=None, coordinates=None, trust=None, user=None):
    """Adds a new row to scrapped_data."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if coordinates is not None:
        if not (isinstance(coordinates, list) and len(coordinates) == 2 and all(isinstance(c, float) for c in coordinates)):
            raise ValueError("coordinates must be a list of two floats: [latitude, longitude]")
        coord_json = json.dumps(coordinates)
    else:
        coord_json = None

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Alerts (date, label, coordinates, trust, user)
        VALUES (?, ?, ?, ?, ?)
    """, (date, label, coord_json, trust, user))
    conn.commit()
    conn.close()
    print("Row added successfully.")


def delete_row(row_id: int):
    """Deletes a row from scrapped_data by ID."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Alerts WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
    print(f"🗑 Row with ID {row_id} deleted (if it existed).")


def view_all():
    """Returns all rows in scrapped_data."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Alerts")
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        row_dict = {
            "id": row["id"],
            "date": row["date"],
            "label": row["label"],
            "coordinates": json.loads(row["coordinates"]) if row["coordinates"] else None,
            "trust": row["trust"],
        }
        result.append(row_dict)
    return result


def row_exists(date, label=None, coordinates=None):
    """Check if a row with the same date, label, and coordinates exists."""
    conn = connect_db()
    cursor = conn.cursor()
    coord_json = json.dumps(coordinates) if coordinates else None

    cursor.execute("""
        SELECT 1 FROM Alerts
        WHERE date = ? AND label = ? AND coordinates = ?
        LIMIT 1
    """, (date, label, coord_json))

    exists = cursor.fetchone() is not None
    conn.close()
    return exists


# --- User Alerts ---

def add_user_alert(email: str, lat: float, lng: float, label: str = "Alert użytkownika"):
    """Adds a user alert to Coordinate table."""
    conn = connect_db()
    cursor = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Ensure user exists
        cursor.execute("INSERT OR IGNORE INTO User (email) VALUES (?)", (email,))

        # Add alert
        cursor.execute("""
            INSERT INTO Coordinate (date, x, y, email)
            VALUES (?, ?, ?, ?)
        """, (date, lat, lng, email))

        conn.commit()
        print(f"Alert użytkownika {email} dodany pomyślnie.")
        return True
    except Exception as e:
        print(f"Błąd podczas dodawania alertu: {e}")
        return False
    finally:
        conn.close()


def get_user_alerts(email: str):
    """Get all alerts for a specific user."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Coordinate WHERE email = ? ORDER BY date DESC", (email,))
    rows = cursor.fetchall()
    conn.close()

    return [{"id": row["id"], "date": row["date"], "x": row["x"], "y": row["y"], "email": row["email"]} for row in rows]


def get_all_alerts():
    """Get all user alerts."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Alerts WHERE User IS NOT NULL;"
                   )
    rows = cursor.fetchall()
    conn.close()

    return [{"id": row["id"], "date": row["date"], "x": row["coordinates"][0], "y": row["coordinates"][1], "email": row["email"]} for row in rows]


# --- Users ---

def add_user(email: str):
    """Adds a new user to User table."""
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
    """Get user by email."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM User WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


if __name__ == '__main__':
    connect_db()
    print("Database initialized successfully.")
