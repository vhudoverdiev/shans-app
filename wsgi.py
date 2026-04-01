from app import create_app
from app.database import init_db
from app.models import init_car_hidden_notifications_table, init_car_notification_archive

init_car_hidden_notifications_table()
init_car_notification_archive()
init_db()

app = create_app()

