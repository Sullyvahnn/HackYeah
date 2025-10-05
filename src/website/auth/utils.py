import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import session, jsonify, request, current_app

JWT_ALGORITHM = "HS256"
JWT_EXP_DELTA_SECONDS = 3600  # 15 minutes
SECRET_KEY = "CHUJ"


def generate_jwt(email):
    payload = {
        "email": email,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_jwt(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = session.get("jwt_token")
        if not token:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401

        payload = verify_jwt(token)
        if not payload:
            session.pop("jwt_token", None)
            return jsonify({"status": "error", "message": "Invalid or expired token"}), 401

        request.user_email = payload["email"]
        return f(*args, **kwargs)
    return decorated
