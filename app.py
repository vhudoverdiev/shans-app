from app import create_app
from app.auth import create_admin_if_not_exists
from app.database import init_db

from app.models import init_car_notification_archive
from app.models import init_car_hidden_notifications_table, init_car_notification_archive

init_car_hidden_notifications_table()
init_car_notification_archive()

init_car_notification_archive()


app = create_app()


if __name__ == "__main__":
    init_db()
    create_admin_if_not_exists()
    print("\n=== ROUTES ===")
    for rule in app.url_map.iter_rules():
        print(rule.endpoint, "->", rule.rule)
    print("==============\n")
    app.run(debug=True)