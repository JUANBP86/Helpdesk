import secrets

from fastapi import HTTPException, Request


async def validar_csrf(request: Request) -> None:
    token_cookie = request.cookies.get("csrf_token")
    formulario = await request.form()
    token_formulario = formulario.get("csrf_token")

    if (
        not token_cookie
        or not isinstance(token_formulario, str)
        or not secrets.compare_digest(token_cookie, token_formulario)
    ):
        raise HTTPException(status_code=403, detail="Solicitud no válida. Recarga la página e inténtalo de nuevo.")


def nuevo_token_csrf() -> str:
    return secrets.token_urlsafe(32)
