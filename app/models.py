from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime,
    ForeignKey, Enum as SAEnum, Boolean, BigInteger
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


# ── Enumeraciones ────────────────────────────────────────────────────────────

class RolUsuario(str, enum.Enum):
    admin   = "admin"
    agente  = "agente"
    usuario = "usuario"


class PrioridadTicket(str, enum.Enum):
    baja    = "baja"
    media   = "media"
    alta    = "alta"
    critica = "critica"


class EstadoTicket(str, enum.Enum):
    abierto    = "abierto"
    en_proceso = "en_proceso"
    resuelto   = "resuelto"
    cerrado    = "cerrado"


# ── Modelos ──────────────────────────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"

    id            = Column(Integer, primary_key=True, index=True)
    nombre        = Column(String(100), nullable=False)
    area          = Column(String(100), nullable=True)
    email         = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol           = Column(SAEnum(RolUsuario), default=RolUsuario.usuario, nullable=False)
    activo        = Column(Boolean, default=True)
    creado_en     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tickets_creados   = relationship("Ticket", back_populates="creador",
                                     foreign_keys="Ticket.creador_id")
    tickets_asignados = relationship("Ticket", back_populates="agente",
                                     foreign_keys="Ticket.agente_id")
    comentarios       = relationship("Comentario", back_populates="autor")
    historial         = relationship("HistorialTicket", back_populates="usuario")


class Categoria(Base):
    __tablename__ = "categorias"

    id     = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(80), unique=True, nullable=False)
    color  = Column(String(7), default="#6366f1")

    tickets = relationship("Ticket", back_populates="categoria")


class Ticket(Base):
    __tablename__ = "tickets"

    id             = Column(Integer, primary_key=True, index=True)
    titulo         = Column(String(200), nullable=False)
    descripcion    = Column(Text, nullable=False)
    estado         = Column(SAEnum(EstadoTicket), default=EstadoTicket.abierto, nullable=False)
    prioridad      = Column(SAEnum(PrioridadTicket), default=PrioridadTicket.media, nullable=False)
    creado_en      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    actualizado_en = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))
    resuelto_en    = Column(DateTime(timezone=True), nullable=True)

    creador_id   = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    agente_id    = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)

    creador     = relationship("Usuario", back_populates="tickets_creados",
                               foreign_keys=[creador_id])
    agente      = relationship("Usuario", back_populates="tickets_asignados",
                               foreign_keys=[agente_id])
    categoria   = relationship("Categoria", back_populates="tickets")
    comentarios = relationship("Comentario", back_populates="ticket",
                               cascade="all, delete-orphan", order_by="Comentario.creado_en")
    historial   = relationship("HistorialTicket", back_populates="ticket",
                               cascade="all, delete-orphan", order_by="HistorialTicket.creado_en")
    adjuntos    = relationship("Adjunto", back_populates="ticket",
                               cascade="all, delete-orphan")


class Comentario(Base):
    __tablename__ = "comentarios"

    id         = Column(Integer, primary_key=True, index=True)
    contenido  = Column(Text, nullable=False)
    es_interno = Column(Boolean, default=False)
    creado_en  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    autor_id  = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    ticket    = relationship("Ticket", back_populates="comentarios")
    autor     = relationship("Usuario", back_populates="comentarios")
    adjuntos  = relationship("Adjunto", back_populates="comentario",
                             cascade="all, delete-orphan")


class HistorialTicket(Base):
    """Registro de cada cambio realizado en un ticket."""
    __tablename__ = "historial_tickets"

    id         = Column(Integer, primary_key=True, index=True)
    campo      = Column(String(50), nullable=False)   # estado, prioridad, agente, categoria
    valor_ant  = Column(String(200), nullable=True)
    valor_nuevo = Column(String(200), nullable=True)
    creado_en  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    ticket_id  = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    ticket  = relationship("Ticket", back_populates="historial")
    usuario = relationship("Usuario", back_populates="historial")


class Adjunto(Base):
    """Archivos adjuntos a tickets o comentarios."""
    __tablename__ = "adjuntos"

    id            = Column(Integer, primary_key=True, index=True)
    nombre_orig   = Column(String(255), nullable=False)   # nombre original del archivo
    nombre_disco  = Column(String(255), nullable=False)   # nombre guardado en disco (uuid)
    mime_type     = Column(String(100), nullable=True)
    tamano        = Column(BigInteger, default=0)          # bytes
    creado_en     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    ticket_id     = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    comentario_id = Column(Integer, ForeignKey("comentarios.id"), nullable=True)
    subido_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    ticket      = relationship("Ticket", back_populates="adjuntos")
    comentario  = relationship("Comentario", back_populates="adjuntos")
    subido_por  = relationship("Usuario")
