from flask import Blueprint, jsonify, request, session
from src.database.db import add_row, get_user_alerts, get_all_alerts
from src.heatmap_algo import create_heatmap
from src.website.auth.utils import verify_jwt

api_bp = Blueprint("api", __name__)
@api_bp.route('/reports', methods=['GET'])
def show_reports():
    alerts = get_all_alerts()
    return jsonify(alerts)
@api_bp.route('/reports', methods=['POST'])
def handle_reports():
    jwt_token = session.get('jwt_token')
    if not jwt_token or not verify_jwt(jwt_token):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    else:
        payload = verify_jwt(jwt_token)

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Brak danych"}), 400

    user_email = payload['email']
    try:
        success = add_row(
            date=data['date'],
            label="Alert użytkownika",
            coordinates=data['coordinates'],
            trust=1,
            user=user_email,
        )

        if success:
            return jsonify({"status": "success", "message": "Alert dodany pomyślnie."})
        else:
            return jsonify({"status": "error", "message": "Błąd podczas dodawania alertu"}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route('/my-alerts')
def get_my_alerts():
    user_email = request.user_email
    alerts = get_user_alerts(user_email)
    return jsonify(alerts)


@api_bp.route('/heatmap', methods=['GET'])
def get_heatmap():
    try:
        heatmap, bounds, grid_info = create_heatmap(
            resolution=100,
            radius_degrees=500.0,
            normalize=True
        )

        if heatmap is None:
            return jsonify({'status': 'error', 'message': 'No data available for heatmap'}), 404

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
        return jsonify({'status': 'error', 'message': str(e)}), 500
