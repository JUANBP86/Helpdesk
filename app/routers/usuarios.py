from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario, RolUsuario
from app.auth import requerir_login, verificar_password, hashear_password
from app.csrf import validar_csrf

router = APIRouter(tags=["usuarios"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/perfil", response_class=HTMLResponse)
async def perfil(
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_login)
):
    return templates.TemplateResponse("perfil.html", {
        "request": request,
        "usuario": usuario_actual,
        "mensaje": None,
        "error": None
    })


@router.post("/perfil", response_class=HTMLResponse, dependencies=[Depends(validar_csrf)])
async def actualizar_perfil(
    request: Request,
    nombre: str = Form(...),
    password_actual: str = Form(""),
    password_nuevo: str = Form(""),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_login)
):
    if password_nuevo and usuario_actual.rol == RolUsuario.usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso para cambiar tu contraseña desde el perfil")

    usuario_actual.nombre = nombre

    if password_nuevo:
        if not verificar_password(password_actual, usuario_actual.password_hash):
            return templates.TemplateResponse("perfil.html", {
                "request": request,
                "usuario": usuario_actual,
                "error": "La contraseña actual no es correcta",
                "mensaje": None
            }, status_code=400)
        usuario_actual.password_hash = hashear_password(password_nuevo)

    db.commit()
    return templates.TemplateResponse("perfil.html", {
        "request": request,
        "usuario": usuario_actual,
        "mensaje": "Perfil actualizado correctamente",
        "error": None
    })
