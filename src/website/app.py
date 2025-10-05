import os
from flask import Flask, render_template
from src.website.auth.routes import auth_bp
from src.website.api.routes import api_bp

SECRET_KEY = "dummy_secret_key_for_development"

def create_app():
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    app = Flask(__name__, template_folder=template_dir)
    app.secret_key = SECRET_KEY

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.route('/')
    def index():
        from src.website.auth.utils import verify_jwt
        from flask import session
        jwt_token = session.get('jwt_token')
        user = None

        if jwt_token:
            payload = verify_jwt(jwt_token)
            if payload:
                user = payload.get('email')

        return render_template('index.html', user_email=user)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
