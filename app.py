from app import create_app
from app.auth import create_admin_if_not_exists
from app.database import init_db


app = create_app()


if __name__ == "__main__":
    init_db()
    create_admin_if_not_exists()
    app.run(debug=True)