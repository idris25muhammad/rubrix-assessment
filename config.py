import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "course_dummy.json")
SECRET_KEY = os.environ.get("RKS_SECRET_KEY", "dev-secret-change-me")
PORT = int(os.environ.get("RKS_PORT", 5000))
APP_NAME = "RubriX"

# Database
DB_ENGINE = os.environ.get("RKS_DB_ENGINE", "mysql")  # "mysql" or "sqlite"
DB_FILE = os.environ.get("RKS_DB_FILE", os.path.join(BASE_DIR, "rubrikrks.db"))
MYSQL_HOST = os.environ.get("RKS_MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("RKS_MYSQL_PORT", 3306))
MYSQL_USER = os.environ.get("RKS_MYSQL_USER", "rubrikrks")
MYSQL_PASSWORD = os.environ.get("RKS_MYSQL_PASSWORD", "rubrikrks_dev_2026")
MYSQL_DB = os.environ.get("RKS_MYSQL_DB", "rubrikrks")

if DB_ENGINE == "mysql":
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
        "?charset=utf8mb4"
    )
else:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_FILE}"
