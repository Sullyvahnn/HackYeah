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
    jwt_token = session.get('jwt_token')
    if not jwt_token:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    payload = verify_jwt(jwt_token)
    if not payload:
        return jsonify({'status': 'error', 'message': 'Invalid token'}), 401
    
    user_email = payload['email']
    alerts = get_user_alerts(user_email)
    return jsonify(alerts)


@api_bp.route('/heatmap', methods=['GET'])
def get_heatmap():
    try:
        # Opcjonalne parametry
        radius = request.args.get('radius', default=500, type=int)
        resolution = request.args.get('resolution', default=100, type=int)
        
        print(f"Generating heatmap with radius={radius}m, resolution={resolution}")
        
        heatmap, bounds, grid_info = create_heatmap(
            radius_meters=radius,
            resolution=resolution,
            normalize=True
        )
        
        if heatmap is None:
            print("Heatmap generation returned None - no data available")
            return jsonify({
                'status': 'error',
                'message': 'No data available for heatmap'
            }), 404
        
        print(f"Heatmap generated successfully: {grid_info['num_points']} points")
        
        # Format zgodny z oczekiwaniami JavaScript
        return jsonify({
            'status': 'ok',
            'message': 'Heatmap generated successfully',
            'data': {
                'heatmap': heatmap.tolist(),
                'bounds': bounds,
                'grid_info': grid_info
            }
        }), 200
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Heatmap error: {e}")
        print(error_trace)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500