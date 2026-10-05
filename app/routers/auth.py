from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models import Usuario, RolUsuario
from app.auth import (
    verificar_password, hashear_password,
    crear_token, obtener_usuario_actual
)
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, COOKIE_SECURE
from app.csrf import validar_csrf

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
limiter = Limiter(key_func=get_remote_address)


@router.get("/", response_class=HTMLResponse)
async def raiz(request: Request, db: Session = Depends(get_db)):
    usuario = obtener_usuario_actual(request, db)
    if usuario:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, db: Session = Depends(get_db)):
    usuario = obtener_usuario_actual(request, db)
    if usuario:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse, dependencies=[Depends(validar_csrf)])
@limiter.limit("5/minute")
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.email == email, Usuario.activo == True).first()
    if not usuario or not verificar_password(password, usuario.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Correo o contraseña incorrectos"},
            status_code=401
        )

    token = crear_token(
        data={"sub": usuario.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=COOKIE_SECURE or request.url.scheme == "https",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout", dependencies=[Depends(validar_csrf)])
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(
        "access_token",
        path="/",
        secure=COOKIE_SECURE or request.url.scheme == "https",
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/registro", response_class=HTMLResponse)
async def registro_get(request: Request, db: Session = Depends(get_db)):
    # Solo permitir registro si no hay usuarios aún (primer uso)
    total = db.query(Usuario).count()
    if total > 0:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("registro.html", {"request": request, "error": None})


@router.post("/registro", response_class=HTMLResponse, dependencies=[Depends(validar_csrf)])
async def registro_post(
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    total = db.query(Usuario).count()
    if total > 0:
        return RedirectResponse(url="/login", status_code=302)

    existente = db.query(Usuario).filter(Usuario.email == email).first()
    if existente:
        return templates.TemplateResponse(
            "registro.html",
            {"request": request, "error": "Ya existe una cuenta con ese correo"},
            status_code=400
        )

    nuevo = Usuario(
        nombre=nombre,
        email=email,
        password_hash=hashear_password(password),
        rol=RolUsuario.admin  # El primer usuario siempre es admin
    )
    db.add(nuevo)
    db.commit()
    return RedirectResponse(url="/login?creado=1", status_code=302)
