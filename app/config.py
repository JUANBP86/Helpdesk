import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:Got0p1%40s@localhost:5432/helpdesk")
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY debe estar configurada con al menos 32 caracteres en .env")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Correo
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

# Sistema
APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8000")
COOKIE_SECURE = os.getenv(
    "COOKIE_SECURE", str(APP_URL.startswith("https://"))
).lower() in ("1", "true", "yes", "on")
DIAS_CIERRE_AUTOMATICO = int(os.getenv("DIAS_CIERRE_AUTOMATICO", "3"))
