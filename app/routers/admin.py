from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Usuario, Categoria, Ticket, RolUsuario
from app.auth import requerir_admin, hashear_password
from app.csrf import validar_csrf

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


# ── Usuarios ─────────────────────────────────────────────────────────────────

@router.get("/usuarios", response_class=HTMLResponse)
async def listar_usuarios(
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requerir_admin)
):
    usuarios = db.query(Usuario).order_by(Usuario.creado_en.desc()).all()
    return templates.TemplateResponse("admin/usuarios.html", {
        "request": request,
        "usuario": admin,
        "usuarios": usuarios,
        "roles": [r.value for r in RolUsuario],
    })


@router.post("/usuarios/nuevo", dependencies=[Depends(validar_csrf)])
async def crear_usuario(
    request: Request,
    nombre: str = Form(...),
    area: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    rol: str = Form(...),
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requerir_admin)
):
    existente = db.query(Usuario).filter(Usuario.email == email).first()
    if existente:
        usuarios = db.query(Usuario).all()
        return templates.TemplateResponse("admin/usuarios.html", {
            "request": request,
            "usuario": admin,
            "usuarios": usuarios,
            "roles": [r.value for r in RolUsuario],
            "error": "Ya existe un usuario con ese correo"
        }, status_code=400)

    area = area.strip()
    if not area:
        raise HTTPException(status_code=400, detail="El área es obligatoria")

    nuevo = Usuario(
        nombre=nombre,
        area=area,
        email=email,
        password_hash=hashear_password(password),
        rol=rol
    )
    db.add(nuevo)
    db.commit()
    return RedirectResponse(url="/admin/usuarios", status_code=302)


@router.get("/usuarios/{usuario_id}/editar", response_class=HTMLResponse)
async def editar_usuario_get(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requerir_admin)
):
    usr = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usr:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("admin/editar_usuario.html", {
        "request": request,
        "usuario": admin,
        "editando": usr,
        "roles": [r.value for r in RolUsuario],
        "error": None,
        "mensaje": None,
    })


@router.post("/usuarios/{usuario_id}/editar", response_class=HTMLResponse, dependencies=[Depends(validar_csrf)])
async def editar_usuario_post(
    usuario_id: int,
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    rol: str = Form(...),
    area: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requerir_admin)
):
    usr = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usr:
        raise HTTPException(status_code=404)

    # Verificar que el email no esté en uso por otro usuario
    existente = db.query(Usuario).filter(
        Usuario.email == email, Usuario.id != usuario_id
    ).first()
    if existente:
        return templates.TemplateResponse("admin/editar_usuario.html", {
            "request": request,
            "usuario": admin,
            "editando": usr,
            "roles": [r.value for r in RolUsuario],
            "error": "Ese correo ya está en uso por otro usuario",
            "mensaje": None,
        }, status_code=400)

    usr.nombre = nombre
    usr.area = area.strip() or None
    usr.email  = email
    usr.rol    = rol

    if password.strip():
        usr.password_hash = hashear_password(password)

    db.commit()
    return templates.TemplateResponse("admin/editar_usuario.html", {
        "request": request,
        "usuario": admin,
        "editando": usr,
        "roles": [r.value for r in RolUsuario],
        "error": None,
        "mensaje": "Usuario actualizado correctamente",
    })


@router.post("/usuarios/{usuario_id}/toggle", dependencies=[Depends(validar_csrf)])
async def toggle_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requerir_admin)
):
    usr = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usr:
        raise HTTPException(status_code=404)
    if usr.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta")
    usr.activo = not usr.activo
    db.commit()
    return RedirectResponse(url="/admin/usuarios", status_code=302)


# ── Categorías ────────────────────────────────────────────────────────────────

@router.get("/categorias", response_class=HTMLResponse)
async def listar_categorias(
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requerir_admin)
):
    categorias = db.query(Categoria).all()
    return templates.TemplateResponse("admin/categorias.html", {
        "request": request,
        "usuario": admin,
        "categorias": categorias,
    })


@router.post("/categorias/nuevo", dependencies=[Depends(validar_csrf)])
async def crear_categoria(
    nombre: str = Form(...),
    color: str = Form("#6366f1"),
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requerir_admin)
):
    cat = Categoria(nombre=nombre, color=color)
    db.add(cat)
    db.commit()
    return RedirectResponse(url="/admin/categorias", status_code=302)


@router.post("/categorias/{cat_id}/eliminar", dependencies=[Depends(validar_csrf)])
async def eliminar_categoria(
    cat_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requerir_admin)
):
    cat = db.query(Categoria).filter(Categoria.id == cat_id).first()
    if cat:
        db.delete(cat)
        db.commit()
    return RedirectResponse(url="/admin/categorias", status_code=302)
