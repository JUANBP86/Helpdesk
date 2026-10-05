import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import (Ticket, Comentario, Categoria, Usuario,
                        EstadoTicket, PrioridadTicket, RolUsuario,
                        HistorialTicket, Adjunto)
from app.auth import requerir_login
from app.csrf import validar_csrf
from app.correo import (correo_ticket_creado, correo_estado_cambiado,
                         correo_comentario_nuevo, correo_ticket_asignado)

router = APIRouter(tags=["tickets"])
templates = Jinja2Templates(directory="app/templates")

ADJUNTOS_DIR = os.path.join("app", "static", "adjuntos")
MAX_TAMANO   = 10 * 1024 * 1024   # 10 MB
TIPOS_PERMITIDOS = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}


def _guardar_adjunto(archivo: UploadFile, contenido: bytes,
                     ticket_id: int, comentario_id: Optional[int],
                     usuario_id: int, db: Session) -> Adjunto:
    ext = os.path.splitext(archivo.filename)[1].lower()
    nombre_disco = f"{uuid.uuid4().hex}{ext}"
    ruta = os.path.join(ADJUNTOS_DIR, nombre_disco)
    with open(ruta, "wb") as f:
        f.write(contenido)
    adj = Adjunto(
        nombre_orig=archivo.filename,
        nombre_disco=nombre_disco,
        mime_type=archivo.content_type,
        tamano=len(contenido),
        ticket_id=ticket_id,
        comentario_id=comentario_id,
        subido_por_id=usuario_id,
    )
    db.add(adj)
    return adj


def _registrar_historial(db: Session, ticket_id: int, usuario_id: int,
                          campo: str, valor_ant: str, valor_nuevo: str):
    if str(valor_ant) != str(valor_nuevo):
        db.add(HistorialTicket(
            ticket_id=ticket_id,
            usuario_id=usuario_id,
            campo=campo,
            valor_ant=str(valor_ant) if valor_ant is not None else "—",
            valor_nuevo=str(valor_nuevo) if valor_nuevo is not None else "—",
        ))


def _horas_abierto(ticket: Ticket) -> float:
    ref = ticket.actualizado_en or ticket.creado_en
    return (datetime.now(timezone.utc) - ref).total_seconds() / 3600


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    estado: Optional[str] = None,
    prioridad: Optional[str] = None,
    buscar: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_login)
):
    query = db.query(Ticket)
    if usuario_actual.rol == RolUsuario.usuario:
        query = query.filter(Ticket.creador_id == usuario_actual.id)
    if estado:
        query = query.filter(Ticket.estado == estado)
    if prioridad:
        query = query.filter(Ticket.prioridad == prioridad)
    if buscar:
        query = query.filter(Ticket.titulo.ilike(f"%{buscar}%"))

    tickets = query.order_by(Ticket.creado_en.desc()).all()

    # Estadísticas
    base = db.query(Ticket)
    if usuario_actual.rol == RolUsuario.usuario:
        base = base.filter(Ticket.creador_id == usuario_actual.id)

    stats = {
        "total":      base.count(),
        "abiertos":   db.query(Ticket).filter(
                          Ticket.estado == EstadoTicket.abierto,
                          *([Ticket.creador_id == usuario_actual.id]
                            if usuario_actual.rol == RolUsuario.usuario else [])
                      ).count(),
        "en_proceso": db.query(Ticket).filter(
                          Ticket.estado == EstadoTicket.en_proceso,
                          *([Ticket.creador_id == usuario_actual.id]
                            if usuario_actual.rol == RolUsuario.usuario else [])
                      ).count(),
        "resueltos":  db.query(Ticket).filter(
                          Ticket.estado == EstadoTicket.resuelto,
                          *([Ticket.creador_id == usuario_actual.id]
                            if usuario_actual.rol == RolUsuario.usuario else [])
                      ).count(),
    }

    # Añadir horas_abierto a cada ticket para alertas de color
    for t in tickets:
        t._horas = _horas_abierto(t)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usuario": usuario_actual,
        "tickets": tickets,
        "stats": stats,
        "filtro_estado": estado,
        "filtro_prioridad": prioridad,
        "buscar": buscar or "",
        "estados": [e.value for e in EstadoTicket],
        "prioridades": [p.value for p in PrioridadTicket],
    })


# ── Nuevo ticket ─────────────────────────────────────────────────────────────

@router.get("/tickets/nuevo", response_class=HTMLResponse)
async def nuevo_ticket_get(
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_login)
):
    categorias = db.query(Categoria).all()
    return templates.TemplateResponse("ticket_form.html", {
        "request": request,
        "usuario": usuario_actual,
        "categorias": categorias,
        "prioridades": (
            [p.value for p in PrioridadTicket]
            if usuario_actual.rol in (RolUsuario.admin, RolUsuario.agente)
            else []
        ),
        "ticket": None,
        "error": None
    })


@router.post("/tickets/nuevo", response_class=HTMLResponse, dependencies=[Depends(validar_csrf)])
async def nuevo_ticket_post(
    request: Request,
    titulo: str = Form(...),
    descripcion: str = Form(...),
    prioridad: Optional[str] = Form(None),
    categoria_id: Optional[str] = Form(None),
    archivos: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_login)
):
    cat_id = int(categoria_id) if categoria_id and categoria_id.strip() else None
    if usuario_actual.rol in (RolUsuario.admin, RolUsuario.agente):
        try:
            prioridad_ticket = PrioridadTicket(prioridad)
        except ValueError:
            raise HTTPException(status_code=400, detail="Prioridad no válida")
    else:
        prioridad_ticket = PrioridadTicket.media

    ticket = Ticket(
        titulo=titulo,
        descripcion=descripcion,
        prioridad=prioridad_ticket,
        categoria_id=cat_id,
        creador_id=usuario_actual.id,
        estado=EstadoTicket.abierto
    )
    db.add(ticket)
    db.flush()   # obtener ticket.id antes del commit

    # Guardar adjuntos
    for archivo in archivos:
        if not archivo.filename:
            continue
        contenido = await archivo.read()
        if len(contenido) > MAX_TAMANO:
            continue
        if archivo.content_type not in TIPOS_PERMITIDOS:
            continue
        _guardar_adjunto(archivo, contenido, ticket.id, None, usuario_actual.id, db)

    db.commit()
    db.refresh(ticket)

    # Notificar a admins y agentes
    destinatarios = db.query(Usuario).filter(
        Usuario.rol.in_([RolUsuario.admin, RolUsuario.agente]),
        Usuario.activo == True
    ).all()
    for dest in destinatarios:
        correo_ticket_creado(dest.email, ticket.id, ticket.titulo, usuario_actual.nombre)

    return RedirectResponse(url=f"/tickets/{ticket.id}", status_code=302)


# ── Ver ticket ───────────────────────────────────────────────────────────────

@router.get("/tickets/{ticket_id}", response_class=HTMLResponse)
async def ver_ticket(
    ticket_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_login)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    if usuario_actual.rol == RolUsuario.usuario and ticket.creador_id != usuario_actual.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    agentes = []
    if usuario_actual.rol in (RolUsuario.admin, RolUsuario.agente):
        agentes = db.query(Usuario).filter(
            Usuario.rol.in_([RolUsuario.agente, RolUsuario.admin]),
            Usuario.activo == True
        ).all()

    categorias = db.query(Categoria).all()

    comentarios = ticket.comentarios
    if usuario_actual.rol == RolUsuario.usuario:
        comentarios = [c for c in comentarios if not c.es_interno]

    return templates.TemplateResponse("ticket_detalle.html", {
        "request": request,
        "usuario": usuario_actual,
        "ticket": ticket,
        "comentarios": comentarios,
        "historial": ticket.historial,
        "adjuntos_ticket": [a for a in ticket.adjuntos if a.comentario_id is None],
        "agentes": agentes,
        "categorias": categorias,
        "estados": [e.value for e in EstadoTicket],
        "prioridades": [p.value for p in PrioridadTicket],
        "horas_abierto": _horas_abierto(ticket),
    })


# ── Comentar ─────────────────────────────────────────────────────────────────

@router.post("/tickets/{ticket_id}/comentar", response_class=HTMLResponse, dependencies=[Depends(validar_csrf)])
async def agregar_comentario(
    ticket_id: int,
    request: Request,
    contenido: str = Form(...),
    es_interno: Optional[str] = Form(None),
    archivos: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_login)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    if usuario_actual.rol == RolUsuario.usuario and ticket.creador_id != usuario_actual.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    interno = es_interno == "true" and usuario_actual.rol != RolUsuario.usuario

    comentario = Comentario(
        contenido=contenido,
        es_interno=interno,
        ticket_id=ticket_id,
        autor_id=usuario_actual.id
    )
    db.add(comentario)
    db.flush()

    # Adjuntos del comentario
    for archivo in archivos:
        if not archivo.filename:
            continue
        contenido_bin = await archivo.read()
        if len(contenido_bin) > MAX_TAMANO or archivo.content_type not in TIPOS_PERMITIDOS:
            continue
        _guardar_adjunto(archivo, contenido_bin, ticket_id, comentario.id, usuario_actual.id, db)

    ticket.actualizado_en = datetime.now(timezone.utc)
    db.commit()

    # Notificaciones (no enviar notas internas al usuario)
    if not interno:
        # Notificar al creador si quien comenta es agente/admin
        if usuario_actual.id != ticket.creador_id:
            correo_comentario_nuevo(
                ticket.creador.email, ticket.id, ticket.titulo,
                usuario_actual.nombre, contenido
            )
        # Notificar al agente asignado si quien comenta es el usuario
        if ticket.agente and usuario_actual.id != ticket.agente_id:
            correo_comentario_nuevo(
                ticket.agente.email, ticket.id, ticket.titulo,
                usuario_actual.nombre, contenido
            )

    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=302)


# ── Actualizar ticket ─────────────────────────────────────────────────────────

@router.post("/tickets/{ticket_id}/actualizar", response_class=HTMLResponse, dependencies=[Depends(validar_csrf)])
async def actualizar_ticket(
    ticket_id: int,
    request: Request,
    estado: str = Form(...),
    prioridad: str = Form(...),
    agente_id: Optional[str] = Form(None),
    categoria_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_login)
):
    if usuario_actual.rol == RolUsuario.usuario:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    nuevo_agente_id  = int(agente_id)   if agente_id   and agente_id.strip()   else None
    nuevo_cat_id     = int(categoria_id) if categoria_id and categoria_id.strip() else None

    # Registrar historial de cambios
    _registrar_historial(db, ticket.id, usuario_actual.id,
                         "estado", ticket.estado, estado)
    _registrar_historial(db, ticket.id, usuario_actual.id,
                         "prioridad", ticket.prioridad, prioridad)

    if ticket.agente_id != nuevo_agente_id:
        ant = ticket.agente.nombre if ticket.agente else "Sin asignar"
        nuevo_agente = db.query(Usuario).filter(Usuario.id == nuevo_agente_id).first() if nuevo_agente_id else None
        nuevo_nombre = nuevo_agente.nombre if nuevo_agente else "Sin asignar"
        _registrar_historial(db, ticket.id, usuario_actual.id, "agente", ant, nuevo_nombre)

        # Notificar al nuevo agente si cambió
        if nuevo_agente:
            correo_ticket_asignado(nuevo_agente.email, ticket.id,
                                   ticket.titulo, ticket.creador.nombre)

    if ticket.categoria_id != nuevo_cat_id:
        ant_cat = ticket.categoria.nombre if ticket.categoria else "Sin categoría"
        nueva_cat = db.query(Categoria).filter(Categoria.id == nuevo_cat_id).first() if nuevo_cat_id else None
        _registrar_historial(db, ticket.id, usuario_actual.id, "categoria",
                              ant_cat, nueva_cat.nombre if nueva_cat else "Sin categoría")

    # Notificar al usuario si el estado cambió
    estado_anterior = ticket.estado
    ticket.estado       = estado
    ticket.prioridad    = prioridad
    ticket.agente_id    = nuevo_agente_id
    ticket.categoria_id = nuevo_cat_id
    ticket.actualizado_en = datetime.now(timezone.utc)

    if estado in (EstadoTicket.resuelto, EstadoTicket.cerrado) and not ticket.resuelto_en:
        ticket.resuelto_en = datetime.now(timezone.utc)

    db.commit()

    if estado_anterior != estado:
        correo_estado_cambiado(ticket.creador.email, ticket.id, ticket.titulo, estado)

    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=302)


# ── Descargar adjunto ─────────────────────────────────────────────────────────

@router.get("/adjuntos/{adjunto_id}")
async def descargar_adjunto(
    adjunto_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_login)
):
    from fastapi.responses import FileResponse
    adj = db.query(Adjunto).filter(Adjunto.id == adjunto_id).first()
    if not adj:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    # Verificar acceso al ticket
    ticket = db.query(Ticket).filter(Ticket.id == adj.ticket_id).first()
    if usuario_actual.rol == RolUsuario.usuario and ticket.creador_id != usuario_actual.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    ruta = os.path.join(ADJUNTOS_DIR, adj.nombre_disco)
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

    return FileResponse(ruta, filename=adj.nombre_orig, media_type=adj.mime_type)
