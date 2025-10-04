import os

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Email
import sqlite3

DB_PATH = os.environ.get('DB_PATH', '../../magiclink.db')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Wyślij link logowania')


# --- DB helpers ---
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
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
    conn.close()


init_db()