import asyncio
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, APP_URL

logger = logging.getLogger(__name__)


async def _enviar(destinatario: str, asunto: str, cuerpo_html: str):
    """Envía un correo HTML por SSL."""
    if not all((SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM)):
        logger.error(
            "No se envió el correo a %s: configura SMTP_HOST, SMTP_USER, "
            "SMTP_PASSWORD y SMTP_FROM en .env",
            destinatario,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = SMTP_FROM
    msg["To"]      = destinatario
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            use_tls=True,          # SSL en puerto 465
        )
        logger.info(f"Correo enviado a {destinatario}: {asunto}")
    except Exception as e:
        logger.error(f"Error enviando correo a {destinatario}: {e}")


def enviar_en_background(destinatario: str, asunto: str, cuerpo_html: str):
    """Lanza el envío sin bloquear la respuesta HTTP."""
    asyncio.create_task(_enviar(destinatario, asunto, cuerpo_html))


# ── Plantillas de correo ──────────────────────────────────────────────────────

def _base_html(contenido: str) -> str:
    return f"""
    <html><body style="font-family:Arial,sans-serif;background:#f3f4f6;padding:20px;">
    <div style="max-width:560px;margin:auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
        <div style="background:#4f46e5;padding:24px 32px;">
            <h1 style="color:white;margin:0;font-size:20px;">Help Desk — ABC Gotuplas</h1>
        </div>
        <div style="padding:28px 32px;">
            {contenido}
        </div>
        <div style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb;">
            <p style="color:#9ca3af;font-size:12px;margin:0;">
                Este es un correo automático, por favor no respondas directamente.<br>
                <a href="{APP_URL}" style="color:#4f46e5;">Ir al Help Desk</a>
            </p>
        </div>
    </div>
    </body></html>
    """


def correo_ticket_creado(email_admin: str, ticket_id: int, titulo: str, creador: str):
    """Notifica a admins/agentes que hay un ticket nuevo."""
    url = f"{APP_URL}/tickets/{ticket_id}"
    cuerpo = f"""
        <h2 style="color:#1f2937;margin-top:0;">Nuevo ticket #{ticket_id}</h2>
        <p style="color:#374151;"><strong>Solicitante:</strong> {creador}</p>
        <p style="color:#374151;"><strong>Título:</strong> {titulo}</p>
        <a href="{url}" style="display:inline-block;margin-top:16px;background:#4f46e5;color:white;
           padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:bold;">
           Ver ticket
        </a>
    """
    enviar_en_background(email_admin, f"[Help Desk] Nuevo ticket #{ticket_id}: {titulo}", _base_html(cuerpo))


def correo_estado_cambiado(email_usuario: str, ticket_id: int, titulo: str, estado_nuevo: str):
    """Notifica al usuario que su ticket cambió de estado."""
    url = f"{APP_URL}/tickets/{ticket_id}"
    estado_fmt = estado_nuevo.replace("_", " ").title()
    colores = {
        "abierto": "#2563eb", "en_proceso": "#d97706",
        "resuelto": "#16a34a", "cerrado": "#6b7280"
    }
    color = colores.get(estado_nuevo, "#4f46e5")
    cuerpo = f"""
        <h2 style="color:#1f2937;margin-top:0;">Tu ticket fue actualizado</h2>
        <p style="color:#374151;"><strong>Ticket:</strong> #{ticket_id} — {titulo}</p>
        <p style="color:#374151;">
            <strong>Nuevo estado:</strong>
            <span style="background:{color}20;color:{color};padding:3px 10px;
                  border-radius:20px;font-weight:bold;">{estado_fmt}</span>
        </p>
        <a href="{url}" style="display:inline-block;margin-top:16px;background:#4f46e5;color:white;
           padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:bold;">
           Ver mi ticket
        </a>
    """
    enviar_en_background(email_usuario, f"[Help Desk] Ticket #{ticket_id} actualizado: {estado_fmt}", _base_html(cuerpo))


def correo_comentario_nuevo(email_dest: str, ticket_id: int, titulo: str, autor: str, contenido: str):
    """Notifica que hay un comentario nuevo en el ticket."""
    url = f"{APP_URL}/tickets/{ticket_id}"
    preview = contenido[:200] + ("..." if len(contenido) > 200 else "")
    cuerpo = f"""
        <h2 style="color:#1f2937;margin-top:0;">Nuevo comentario en ticket #{ticket_id}</h2>
        <p style="color:#374151;"><strong>Ticket:</strong> {titulo}</p>
        <p style="color:#374151;"><strong>De:</strong> {autor}</p>
        <div style="background:#f9fafb;border-left:4px solid #4f46e5;padding:12px 16px;
             border-radius:4px;margin:16px 0;color:#374151;">
            {preview}
        </div>
        <a href="{url}" style="display:inline-block;background:#4f46e5;color:white;
           padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:bold;">
           Ver conversación
        </a>
    """
    enviar_en_background(email_dest, f"[Help Desk] Nuevo comentario en ticket #{ticket_id}", _base_html(cuerpo))


def correo_ticket_asignado(email_agente: str, ticket_id: int, titulo: str, creador: str):
    """Notifica al agente que le asignaron un ticket."""
    url = f"{APP_URL}/tickets/{ticket_id}"
    cuerpo = f"""
        <h2 style="color:#1f2937;margin-top:0;">Te asignaron un ticket</h2>
        <p style="color:#374151;"><strong>Ticket:</strong> #{ticket_id} — {titulo}</p>
        <p style="color:#374151;"><strong>Solicitante:</strong> {creador}</p>
        <a href="{url}" style="display:inline-block;margin-top:16px;background:#4f46e5;color:white;
           padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:bold;">
           Atender ticket
        </a>
    """
    enviar_en_background(email_agente, f"[Help Desk] Ticket #{ticket_id} asignado a ti", _base_html(cuerpo))


def correo_ticket_cerrado_auto(email_usuario: str, ticket_id: int, titulo: str):
    """Notifica al usuario que su ticket fue cerrado automáticamente."""
    url = f"{APP_URL}/tickets/{ticket_id}"
    cuerpo = f"""
        <h2 style="color:#1f2937;margin-top:0;">Ticket cerrado automáticamente</h2>
        <p style="color:#374151;">Tu ticket <strong>#{ticket_id} — {titulo}</strong> fue cerrado
        automáticamente porque lleva más de 3 días en estado "Resuelto" sin actividad.</p>
        <p style="color:#374151;">Si el problema persiste, puedes abrir un nuevo ticket.</p>
        <a href="{APP_URL}/tickets/nuevo" style="display:inline-block;margin-top:16px;
           background:#4f46e5;color:white;padding:10px 20px;border-radius:8px;
           text-decoration:none;font-weight:bold;">
           Abrir nuevo ticket
        </a>
    """
    enviar_en_background(email_usuario, f"[Help Desk] Ticket #{ticket_id} cerrado automáticamente", _base_html(cuerpo))
