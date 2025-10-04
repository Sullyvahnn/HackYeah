import os

import uuid
import time
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, flash


from src.website.user_db.db import LoginForm, get_db

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')


SMTP_HOST = os.environ.get('SMTP_HOST', 'localhost')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 1025))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'no-reply@example.com')

HOST_URL = os.environ.get('HOST_URL', 'http://127.0.0.1:5000')
TOKEN_TTL = 15 * 60
# -----------------------------------

app = Flask(__name__)
app.secret_key = SECRET_KEY


# --- Formularz logowania ---



# --- Email sender ---
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


# --- Routes ---
@app.route('/')
def index():
    user = session.get('user_email')
    return render_template('index.html', user_email=user)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        # Generuj token
        token = uuid.uuid4().hex
        now = int(time.time())

        # Zapisz token do bazy
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO tokens(token,email,created_at,used) VALUES (?,?,?,0)", (token, email, now))
        conn.commit()
        conn.close()

        # Wyślij email
        if send_magic_link_email(email, token):
            return render_template('login_success.html', email=email)
        else:
            flash("Błąd podczas wysyłania emaila. Spróbuj ponownie.")

    return render_template("login.html", form=form)


@app.route('/magic/<token>')
def magic(token):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tokens WHERE token=?", (token,))
    row = cur.fetchone()

    if not row:
        return render_template_string("<h1>Błąd</h1><p>Nieprawidłowy link.</p>")

    if row['used']:
        return render_template_string("<h1>Błąd</h1><p>Link już został użyty.</p>")

    if time.time() - row['created_at'] > TOKEN_TTL:
        return render_template_string("<h1>Błąd</h1><p>Link wygasł.</p>")

    # Oznacz token jako użyty i zapisz sesję
    cur.execute("UPDATE tokens SET used=1 WHERE token=?", (token,))
    conn.commit()
    conn.close()

    session['user_email'] = row['email']
    flash("Zalogowano pomyślnie!")
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.pop('user_email', None)
    flash("Wylogowano pomyślnie!")
    return redirect(url_for('index'))


# --- API do raportów ---
reports_data = []  # Tymczasowe przechowywanie alertów


@app.route('/api/reports', methods=['GET', 'POST'])
def reports():
    if request.method == 'POST':
        data = request.get_json()
        print("Nowy alert:", data)
        reports_data.append(data)
        return {"status": "ok"}
    return reports_data


if __name__ == '__main__':
    app.run(debug=True)