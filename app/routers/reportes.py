from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import requerir_agente_o_admin
from app.database import get_db
from app.models import (
    Categoria,
    EstadoTicket,
    PrioridadTicket,
    RolUsuario,
    Ticket,
    Usuario,
)

router = APIRouter(tags=["reportes"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard/reportes", response_class=HTMLResponse)
async def dashboard_reportes(
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(requerir_agente_o_admin),
):
    conteo_categoria = (
        db.query(Categoria.nombre, func.count(Ticket.id))
        .outerjoin(Ticket, Ticket.categoria_id == Categoria.id)
        .group_by(Categoria.id, Categoria.nombre)
        .all()
    )
    categorias = [
        {"nombre": nombre, "total": total}
        for nombre, total in conteo_categoria
    ]
    sin_categoria = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.categoria_id.is_(None))
        .scalar()
        or 0
    )
    if sin_categoria:
        categorias.append({"nombre": "Sin categoría", "total": sin_categoria})
    categorias.sort(key=lambda categoria: (-categoria["total"], categoria["nombre"].lower()))

    estados = {estado.value: 0 for estado in EstadoTicket}
    estados.update({
        estado.value: total
        for estado, total in db.query(Ticket.estado, func.count(Ticket.id))
        .group_by(Ticket.estado)
        .all()
    })

    prioridades = {prioridad.value: 0 for prioridad in PrioridadTicket}
    prioridades.update({
        prioridad.value: total
        for prioridad, total in db.query(Ticket.prioridad, func.count(Ticket.id))
        .group_by(Ticket.prioridad)
        .all()
    })

    agentes = [
        {"nombre": nombre, "total": total}
        for nombre, total in (
            db.query(Usuario.nombre, func.count(Ticket.id))
            .outerjoin(Ticket, Ticket.agente_id == Usuario.id)
            .filter(Usuario.rol.in_([RolUsuario.admin, RolUsuario.agente]))
            .group_by(Usuario.id, Usuario.nombre)
            .order_by(func.count(Ticket.id).desc(), Usuario.nombre)
            .all()
        )
    ]
    sin_asignar = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.agente_id.is_(None))
        .scalar()
        or 0
    )
    if sin_asignar:
        agentes.append({"nombre": "Sin asignar", "total": sin_asignar})

    hoy = datetime.now(timezone.utc).date()
    primer_dia = hoy - timedelta(days=29)
    fin_periodo = hoy + timedelta(days=1)
    inicio = datetime.combine(primer_dia, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(fin_periodo, time.min, tzinfo=timezone.utc)
    tickets_diarios = (
        db.query(Ticket.creado_en)
        .filter(Ticket.creado_en >= inicio, Ticket.creado_en < fin)
        .all()
    )
    volumen_por_dia = {primer_dia + timedelta(days=i): 0 for i in range(30)}
    for (creado_en,) in tickets_diarios:
        dia = creado_en.date()
        if dia in volumen_por_dia:
            volumen_por_dia[dia] += 1

    resueltos = (
        db.query(Ticket.creado_en, Ticket.resuelto_en)
        .filter(
            Ticket.estado.in_([EstadoTicket.resuelto, EstadoTicket.cerrado]),
            Ticket.resuelto_en.is_not(None),
        )
        .all()
    )
    tiempos_resolucion = [
        (resuelto_en - creado_en).total_seconds() / 3600
        for creado_en, resuelto_en in resueltos
        if resuelto_en >= creado_en
    ]
    cantidad_resueltos = len(tiempos_resolucion)
    promedio_resolucion = (
        sum(tiempos_resolucion) / cantidad_resueltos if cantidad_resueltos else None
    )
    porcentaje_sla = (
        sum(tiempo < 24 for tiempo in tiempos_resolucion) * 100 / cantidad_resueltos
        if cantidad_resueltos
        else None
    )

    return templates.TemplateResponse("dashboard_reportes.html", {
        "request": request,
        "usuario": usuario_actual,
        "categorias": categorias,
        "estados": estados,
        "prioridades": prioridades,
        "agentes": agentes,
        "fechas_volumen": [dia.strftime("%d/%m") for dia in volumen_por_dia],
        "volumen_diario": list(volumen_por_dia.values()),
        "promedio_resolucion": promedio_resolucion,
        "porcentaje_sla": porcentaje_sla,
        "cantidad_resueltos": cantidad_resueltos,
    })
