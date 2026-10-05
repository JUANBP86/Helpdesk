"""
Tareas programadas que corren en segundo plano mientras el servidor está activo.
"""
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Ticket, EstadoTicket, HistorialTicket
from app.correo import correo_ticket_cerrado_auto
from app.config import DIAS_CIERRE_AUTOMATICO

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


async def cerrar_tickets_resueltos():
    """
    Cierra automáticamente los tickets que llevan más de DIAS_CIERRE_AUTOMATICO
    días en estado 'resuelto' sin actividad.
    Corre cada hora.
    """
    db: Session = SessionLocal()
    try:
        limite = datetime.now(timezone.utc) - timedelta(days=DIAS_CIERRE_AUTOMATICO)

        tickets = db.query(Ticket).filter(
            Ticket.estado == EstadoTicket.resuelto,
            Ticket.actualizado_en <= limite
        ).all()

        for ticket in tickets:
            logger.info(f"Cerrando automáticamente ticket #{ticket.id}: {ticket.titulo}")

            # Registrar en historial
            db.add(HistorialTicket(
                ticket_id=ticket.id,
                usuario_id=ticket.creador_id,   # se registra como acción del sistema
                campo="estado",
                valor_ant="resuelto",
                valor_nuevo="cerrado",
            ))

            ticket.estado = EstadoTicket.cerrado
            ticket.actualizado_en = datetime.now(timezone.utc)

            # Notificar al usuario
            correo_ticket_cerrado_auto(
                ticket.creador.email,
                ticket.id,
                ticket.titulo
            )

        if tickets:
            db.commit()
            logger.info(f"Cierre automático: {len(tickets)} ticket(s) cerrados.")

    except Exception as e:
        logger.error(f"Error en cierre automático: {e}")
        db.rollback()
    finally:
        db.close()


def iniciar_scheduler():
    """Registra las tareas y arranca el scheduler."""
    scheduler.add_job(
        cerrar_tickets_resueltos,
        trigger="interval",
        hours=1,
        id="cierre_automatico",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc)  # corre también al iniciar
    )
    scheduler.start()
    logger.info("Scheduler iniciado — cierre automático cada 1 hora.")


def detener_scheduler():
    """Detiene el scheduler limpiamente al apagar el servidor."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido.")
