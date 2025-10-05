import os
import uuid
import time
import smtplib
from email.message import EmailMessage
from flask import Blueprint, render_template, render_template_string, request, redirect, url_for, session, flash
from src.database.db import connect_db, LoginForm
from src.website.auth.utils import generate_jwt

auth_bp = Blueprint("auth", __name__)

# Config
SMTP_HOST = os.environ.get('SMTP_HOST', 'localhost')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 1025))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'no-reply@example.com')
HOST_URL = os.environ.get('HOST_URL', 'http://127.0.0.1:5000')
TOKEN_TTL = 3600


def send_magic_link_email(to_email, token):
    link = f"{HOST_URL}/magic/{token}"
    msg = EmailMessage()
    msg['Subject'] = 'Twój link logowania do DangerMap'
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    msg.set_content(f"""Kliknij poniższy link aby się zalogować:
{link}

Link jest ważny przez 15 minut.""")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            if SMTP_USER and SMTP_PASS:
                smtp.starttls()
                smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"Błąd wysyłki email: {e}")
        return False


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        token = uuid.uuid4().hex
        now = int(time.time())

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO tokens(token,email,created_at,used) VALUES (?,?,?,0)", (token, email, now))
        conn.commit()
        conn.close()

        if send_magic_link_email(email, token):
            return render_template('login_success.html', email=email)
        else:
            flash("Błąd podczas wysyłania emaila. Spróbuj ponownie.")
    return render_template("login.html", form=form)


@auth_bp.route('/magic/<token>')
def magic(token):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tokens WHERE token = ?", (token,))
    row = cur.fetchone()

    if not row:
        return render_template_string("<h1>Błąd</h1><p>Nieprawidłowy link.</p>")
    if row['used']:
        return render_template_string("<h1>Błąd</h1><p>Link już został użyty.</p>")
    if time.time() - row['created_at'] > TOKEN_TTL:
        return render_template_string("<h1>Błąd</h1><p>Link wygasł.</p>")

    cur.execute("UPDATE tokens SET used=1 WHERE token=?", (token,))
    conn.commit()
    conn.close()

    jwt_token = generate_jwt(row['email'])
    session['jwt_token'] = jwt_token

    return redirect(url_for('index'))


@auth_bp.route('/logout')
def logout():
    session.pop('jwt_token', None)
    flash("Wylogowano pomyślnie.")
    return redirect(url_for('index'))
