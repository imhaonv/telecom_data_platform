# superset/init_superset.py
import requests
import json
import time

# Configuration
SUPERSET_URL = "http://localhost:8082"
USERNAME = "admin"
PASSWORD = "admin"


def login():
    """Đăng nhập vào Superset"""
    session = requests.Session()
    login_data = {"username": USERNAME, "password": PASSWORD, "provider": "db"}

    response = session.post(f"{SUPERSET_URL}/api/v1/security/login", json=login_data)
    response.raise_for_status()

    access_token = response.json()["access_token"]
    session.headers.update(
        {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    )

    return session


def create_database(session):
    """Tạo database connection trong Superset"""
    db_config = {
        "database_name": "Telecom Data Platform",
        "sqlalchemy_uri": "postgresql://admin:admin123@postgres:5432/telecom_data",
        "extra": json.dumps(
            {"engine_params": {"connect_args": {"sslmode": "require"}}}
        ),
    }

    response = session.post(f"{SUPERSET_URL}/api/v1/database/", json=db_config)
    return response.json()


def create_dashboards(session):
    """Tạo dashboards mẫu"""

    # 1. Daily Registration Dashboard
    daily_dashboard = {
        "dashboard_title": "Telecom Daily Subscriptions",
        "slug": "telecom-daily",
        "position_json": json.dumps(
            {
                "DASHBOARD_VERSION_KEY": "v2",
                "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
                "GRID_ID": {
                    "type": "GRID",
                    "id": "GRID_ID",
                    "children": ["ROW-1", "ROW-2", "ROW-3"],
                    "parents": ["ROOT_ID"],
                },
            }
        ),
        "css": "",
        "json_metadata": json.dumps(
            {
                "timed_refresh_immune_slices": [],
                "expanded_slices": {},
                "refresh_frequency": 900,
                "default_filters": json.dumps({}),
                "color_scheme": "supersetColors",
            }
        ),
        "published": True,
    }

    response = session.post(f"{SUPERSET_URL}/api/v1/dashboard/", json=daily_dashboard)
    return response.json()


if __name__ == "__main__":
    print("Initializing Superset...")
    time.sleep(30)  # Chờ Superset khởi động

    try:
        session = login()
        print("Logged in to Superset")

        db = create_database(session)
        print(f"Database created: {db}")

        dashboard = create_dashboards(session)
        print(f"Dashboard created: {dashboard}")

    except Exception as e:
        print(f"Error: {e}")
