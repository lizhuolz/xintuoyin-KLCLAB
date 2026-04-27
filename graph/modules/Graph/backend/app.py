from pathlib import Path

from flask import Flask, send_from_directory

from .api.routes import api_bp
from .config import settings

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / 'frontend'


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR / 'assets'),
        template_folder=str(FRONTEND_DIR),
    )
    app.register_blueprint(api_bp)

    @app.get('/')
    def index():
        return send_from_directory(FRONTEND_DIR, 'index.html')

    @app.get('/<path:path>')
    def frontend_files(path: str):
        target = FRONTEND_DIR / path
        if target.exists() and target.is_file():
            return send_from_directory(FRONTEND_DIR, path)
        return send_from_directory(FRONTEND_DIR, 'index.html')

    return app


app = create_app()


if __name__ == '__main__':
    app.run(host=settings.host, port=settings.port, debug=settings.debug)
