import os

import uuid
import time
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, flash, jsonify
from src.database.db import add_user_alert, get_user_alerts, get_all_alerts
from src.database.db import LoginForm, connect_db
from src.heatmap_algo import create_heatmap

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
        conn = connect_db()
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
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tokens WHERE token = ?", (token,))
    row = cur.fetchone()
    print(row)

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
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('index'))


# --- API do raportów ---
reports_data = []  # Tymczasowe przechowywanie alertów


@app.route('/api/reports', methods=['GET', 'POST'])
def handle_reports():
    if request.method == 'GET':
        alerts = get_all_alerts()
        return jsonify(alerts)

    elif request.method == 'POST':
        if not session.get('user_email'):
            return jsonify({"status": "error", "message": "Nie jesteś zalogowany/a"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Brak danych"}), 400

        user_email = session['user_email']

        try:
            success = add_user_alert(
                email=user_email,
                lat=data['lat'],
                lng=data['lng'],
                label="Alert użytkownika"
            )

            if success:
                return jsonify({"status": "success", "message": "Alert dodany pomyślnie."})
            else:
                return jsonify({"status": "error", "message": "Błąd podczas dodawania alertu"}), 500

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return None


@app.route('/api/my-alerts')
def get_my_alerts():
    if not session.get('user_email'):
        return jsonify([])

    user_email = session['user_email']
    alerts = get_user_alerts(user_email)
    return jsonify(alerts)



@app.route('/api/heatmap', methods=['GET'])
def get_heatmap():
    try:
        # Generate heatmap with specified parameters
        heatmap, bounds, grid_info = create_heatmap(
            resolution=100,
            radius_degrees=500.0,
            normalize=True
        )

        if heatmap is None:
            return jsonify({
                'status': 'error',
                'message': 'No data available for heatmap'
            }), 404

        # Return properly structured response
        return jsonify({
            'status': 'ok',
            'data': {
                'heatmap': heatmap.tolist(),
                'bounds': bounds,
                'grid_info': grid_info
            }
        })

    except Exception as e:
        print(f"Heatmap error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)