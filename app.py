# REVIEW: Legacy root entry point instantiating the Flask application via create_app().
"""Legacy entrypoint.

Phase 1 refactor moves routes into Blueprints under app/*.
This file remains only to run the app directly (python app.py).
"""

from app import create_app

app = create_app()


if __name__ == '__main__':
    # REVIEW: dev entrypoint only — production serves via gunicorn/Vercel (api/index.py).
    # REVIEW: debug must never default on; CodeQL flags it as RCE-adjacent (py/flask-debug).
    import os
    app.run(debug=os.environ.get('FLASK_ENV') == 'development')
