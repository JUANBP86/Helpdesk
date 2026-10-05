from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db
from app.models import Usuario

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verificar_password(password_plano: str, password_hash: str) -> bool:
    return pwd_context.verify(password_plano, password_hash)


def hashear_password(password: str) -> str:
    return pwd_context.hash(password)


def crear_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def obtener_usuario_actual(request: Request, db: Session = Depends(get_db)) -> Optional[Usuario]:
    """Lee el token de la cookie y devuelve el usuario, o None si no hay sesión."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None

    usuario = db.query(Usuario).filter(Usuario.email == email, Usuario.activo == True).first()
    return usuario


def requerir_login(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """Dependency: redirige al login si no hay sesión activa."""
    usuario = obtener_usuario_actual(request, db)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                            headers={"Location": "/login"})
    return usuario


def requerir_admin(request: Request, db: Session = Depends(get_db)) -> Usuario:
    usuario = requerir_login(request, db)
    if usuario.rol != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return usuario


def requerir_agente_o_admin(request: Request, db: Session = Depends(get_db)) -> Usuario:
    usuario = requerir_login(request, db)
    if usuario.rol not in ("admin", "agente"):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return usuario
