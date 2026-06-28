"""Legacy entrypoint.

Phase 1 refactor moves routes into Blueprints under app/*.
This file remains only to run the app directly (python app.py).
"""

from app import create_app

app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
