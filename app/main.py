from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
from sqlalchemy import inspect, text
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import engine, Base
from app.routers import auth, tickets, admin, usuarios, reportes
from app.tareas import iniciar_scheduler, detener_scheduler
from app.csrf import nuevo_token_csrf
from app.config import COOKIE_SECURE

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)
if "area" not in {column["name"] for column in inspect(engine).get_columns("usuarios")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE usuarios ADD COLUMN area VARCHAR(100)"))

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranque y apagado limpio del servidor."""
    iniciar_scheduler()
    yield
    detener_scheduler()


app = FastAPI(
    title="Help Desk",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def seguridad_respuesta(request: Request, call_next):
    es_estatico = request.url.path.startswith("/static/")
    token_csrf = request.cookies.get("csrf_token")
    emitir_cookie_csrf = not es_estatico and not token_csrf
    if emitir_cookie_csrf:
        token_csrf = nuevo_token_csrf()
    request.state.csrf_token = token_csrf or ""

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    if emitir_cookie_csrf:
        response.set_cookie(
            key="csrf_token",
            value=token_csrf,
            httponly=True,
            secure=COOKIE_SECURE or request.url.scheme == "https",
            samesite="lax",
            path="/",
        )
    return response


# Archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routers
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(admin.router)
app.include_router(usuarios.router)
app.include_router(reportes.router)
