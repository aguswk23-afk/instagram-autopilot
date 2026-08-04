"""
Ejecutor de tareas (Scheduler).

Proceso de fondo que revisa periódicamente la base de datos en busca de
publicaciones pendientes cuya hora programada ya se cumplió, y las publica
automáticamente a través del motor de publicación (instagram_api.py).
"""

import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

import config
import database
import instagram_api

logger = logging.getLogger(__name__)


def procesar_posts_pendientes():
    """
    Tarea principal ejecutada periódicamente por el scheduler: busca posts
    PENDING listos para publicarse (scheduled_time <= ahora) y los procesa
    uno a uno.
    """
    ahora = datetime.utcnow()
    posts_listos = database.obtener_posts_pendientes_listos(ahora)

    if not posts_listos:
        logger.debug("No hay posts pendientes listos para publicar en este ciclo.")
        return

    logger.info("Se encontraron %d post(s) listos para publicar.", len(posts_listos))

    for post in posts_listos:
        _procesar_un_post(post)


def _procesar_un_post(post: database.Post):
    """
    Procesa la publicación de un post individual, actualizando su estado
    en la base de datos en cada etapa (PROCESSING -> PUBLISHED/FAILED).
    """
    logger.info("Procesando post id=%s (%s)...", post.id, post.media_type)
    database.actualizar_estado_post(post.id, database.PostStatus.PROCESSING)

    try:
        resultado = instagram_api.publicar_post_completo(
            media_url=post.media_url,
            caption=post.caption,
            media_type=post.media_type,
        )
        database.actualizar_estado_post(
            post.id,
            database.PostStatus.PUBLISHED,
            ig_container_id=resultado["creation_id"],
            ig_media_id=resultado["media_id"],
        )
        logger.info("Post id=%s publicado exitosamente (media_id=%s).", post.id, resultado["media_id"])

    except instagram_api.TokenExpiradoError as error:
        # Error crítico de credenciales: se detiene el ciclo actual para no
        # seguir fallando contra el resto de los posts con el mismo token.
        logger.critical("El access token expiró. Se detiene el ciclo actual: %s", error)
        database.actualizar_estado_post(post.id, database.PostStatus.FAILED, error_message=str(error))
        raise

    except instagram_api.RateLimitError as error:
        # Se marca como fallido; se puede reintentar en un ciclo futuro
        # reestableciendo manualmente su estado a PENDING si se desea.
        logger.warning("Rate limit alcanzado al publicar post id=%s: %s", post.id, error)
        database.actualizar_estado_post(post.id, database.PostStatus.FAILED, error_message=str(error))

    except instagram_api.InstagramAPIError as error:
        logger.error("Error al publicar post id=%s: %s", post.id, error)
        database.actualizar_estado_post(post.id, database.PostStatus.FAILED, error_message=str(error))

    except Exception as error:  # Cualquier error no anticipado también se registra.
        logger.exception("Error inesperado al procesar el post id=%s.", post.id)
        database.actualizar_estado_post(post.id, database.PostStatus.FAILED, error_message=str(error))


def iniciar_scheduler():
    """
    Configura e inicia el scheduler en modo bloqueante, ejecutando
    `procesar_posts_pendientes` cada `SCHEDULER_INTERVAL_MINUTES` minutos.
    """
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        procesar_posts_pendientes,
        "interval",
        minutes=config.SCHEDULER_INTERVAL_MINUTES,
        id="revisar_posts_pendientes",
        next_run_time=datetime.utcnow(),  # Ejecuta una primera revisión inmediata al iniciar.
    )

    logger.info(
        "Scheduler iniciado. Revisando la base de datos cada %d minuto(s). Presiona Ctrl+C para detener.",
        config.SCHEDULER_INTERVAL_MINUTES,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler detenido por el usuario.")
