"""
Motor de publicación.

Implementa la comunicación con la Instagram Graph API para publicar
contenido (imágenes y Reels) usando el flujo asíncrono oficial de Meta,
en 3 pasos:

    1. Crear un contenedor de media   -> POST /{ig-user-id}/media
    2. Consultar el estado del contenedor hasta que esté FINISHED
    3. Publicar el contenedor         -> POST /{ig-user-id}/media_publish
"""

import logging
import time

import requests

import config

logger = logging.getLogger(__name__)


class InstagramAPIError(Exception):
    """Excepción base para errores al interactuar con la Graph API."""
    pass


class TokenExpiradoError(InstagramAPIError):
    """El access token venció o fue revocado (error OAuth, código 190)."""
    pass


class RateLimitError(InstagramAPIError):
    """Se alcanzó el límite de solicitudes de la API (rate limiting)."""
    pass


class MediaProcessingError(InstagramAPIError):
    """El contenedor de media terminó en estado ERROR (ej: formato inválido)."""
    pass


class MediaProcessingTimeoutError(InstagramAPIError):
    """El contenedor de media no terminó de procesarse dentro del tiempo máximo permitido."""
    pass


def _manejar_error_http(respuesta: requests.Response):
    """
    Inspecciona una respuesta de error de la Graph API y lanza la excepción
    específica correspondiente, para que las capas superiores (scheduler)
    puedan reaccionar de forma diferenciada (reintentar, marcar fallido, etc).
    """
    try:
        cuerpo = respuesta.json()
        error = cuerpo.get("error", {})
        codigo = error.get("code")
        subcodigo = error.get("error_subcode")
        mensaje = error.get("message", respuesta.text)
    except ValueError:
        codigo = None
        subcodigo = None
        mensaje = respuesta.text

    logger.error("Error de la Graph API (HTTP %s): %s", respuesta.status_code, mensaje)

    # Código 190 = OAuthException (token inválido o expirado).
    if codigo == 190:
        raise TokenExpiradoError(f"El access token es inválido o expiró: {mensaje}")

    # Códigos 4 / 17 / 32, o HTTP 429, suelen indicar límites de uso de la API.
    if codigo in (4, 17, 32) or respuesta.status_code == 429:
        raise RateLimitError(f"Se alcanzó un límite de la API (rate limit): {mensaje}")

    raise InstagramAPIError(
        f"Error inesperado de la Graph API (código {codigo}, subcódigo {subcodigo}): {mensaje}"
    )


def crear_contenedor_media(media_url: str, caption: str, media_type: str) -> str:
    """
    Paso 1: crea un contenedor de media en los servidores de Meta a partir
    de una URL pública de imagen o video.

    Retorna el `creation_id` (id del contenedor) usado en los siguientes pasos.
    """
    url = f"{config.GRAPH_API_BASE_URL}/{config.IG_ACCOUNT_ID}/media"

    payload = {
        "caption": caption or "",
        "access_token": config.ACCESS_TOKEN,
    }

    if media_type == "REEL":
        payload["media_type"] = "REELS"
        payload["video_url"] = media_url
    else:  # IMAGE
        payload["image_url"] = media_url

    logger.info("Creando contenedor de media (%s)...", media_type)

    try:
        respuesta = requests.post(url, data=payload, timeout=30)
    except requests.exceptions.RequestException as error:
        raise InstagramAPIError(f"Error de conexión al crear el contenedor: {error}") from error

    if not respuesta.ok:
        _manejar_error_http(respuesta)

    creation_id = respuesta.json().get("id")
    if not creation_id:
        raise InstagramAPIError("La API no devolvió un id de contenedor válido.")

    logger.info("Contenedor creado exitosamente. creation_id=%s", creation_id)
    return creation_id


def esperar_procesamiento_contenedor(creation_id: str) -> None:
    """
    Paso 2: consulta repetidamente el estado del contenedor (`status_code`)
    hasta que sea FINISHED, ERROR, o se agote el número máximo de intentos.

    Es el paso vital para Reels/videos pesados, que Meta procesa de forma
    asíncrona en sus servidores tras la creación del contenedor.
    """
    url = f"{config.GRAPH_API_BASE_URL}/{creation_id}"
    params = {
        "fields": "status_code",
        "access_token": config.ACCESS_TOKEN,
    }

    for intento in range(1, config.MEDIA_STATUS_MAX_ATTEMPTS + 1):
        try:
            respuesta = requests.get(url, params=params, timeout=15)
        except requests.exceptions.RequestException as error:
            raise InstagramAPIError(
                f"Error de conexión al consultar el estado del contenedor: {error}"
            ) from error

        if not respuesta.ok:
            _manejar_error_http(respuesta)

        status_code = respuesta.json().get("status_code")
        logger.info(
            "Estado del contenedor %s (intento %d/%d): %s",
            creation_id, intento, config.MEDIA_STATUS_MAX_ATTEMPTS, status_code,
        )

        if status_code == "FINISHED":
            return
        if status_code == "ERROR":
            raise MediaProcessingError(f"El contenedor {creation_id} terminó en estado ERROR.")

        # IN_PROGRESS o EXPIRED: se espera y se reintenta.
        time.sleep(config.MEDIA_STATUS_POLL_INTERVAL_SECONDS)

    raise MediaProcessingTimeoutError(
        f"El contenedor {creation_id} no terminó de procesarse tras "
        f"{config.MEDIA_STATUS_MAX_ATTEMPTS} intentos."
    )


def publicar_contenedor(creation_id: str) -> str:
    """
    Paso 3: publica el contenedor ya procesado (status FINISHED) en el
    feed de Instagram.

    Retorna el id final de la publicación (media_id).
    """
    url = f"{config.GRAPH_API_BASE_URL}/{config.IG_ACCOUNT_ID}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": config.ACCESS_TOKEN,
    }

    logger.info("Publicando contenedor %s...", creation_id)

    try:
        respuesta = requests.post(url, data=payload, timeout=30)
    except requests.exceptions.RequestException as error:
        raise InstagramAPIError(f"Error de conexión al publicar el contenedor: {error}") from error

    if not respuesta.ok:
        _manejar_error_http(respuesta)

    media_id = respuesta.json().get("id")
    if not media_id:
        raise InstagramAPIError("La API no devolvió un id de publicación válido.")

    logger.info("Publicación realizada exitosamente. media_id=%s", media_id)
    return media_id


def publicar_post_completo(media_url: str, caption: str, media_type: str) -> dict:
    """
    Orquesta el flujo completo de 3 pasos para publicar un post:
    crear contenedor -> esperar procesamiento -> publicar.

    Retorna un diccionario con `creation_id` y `media_id`, útil para
    guardar en la base de datos como registro de auditoría.
    """
    creation_id = crear_contenedor_media(media_url, caption, media_type)
    esperar_procesamiento_contenedor(creation_id)
    media_id = publicar_contenedor(creation_id)

    return {
        "creation_id": creation_id,
        "media_id": media_id,
    }
