"""
Script de ejemplo / CLI para programar nuevos posts.

Permite cargar un post en la base de datos indicando manualmente el
horario, o bien dejar que el módulo `analytics` sugiera automáticamente
el mejor horario según las horas pico de la audiencia.

Ejemplos de uso:

    # Sugerir automáticamente el horario según la audiencia:
    python agregar_post.py --url "https://mi-cdn.com/foto.jpg" \
        --caption "Nuevo lanzamiento 🚀" --tipo IMAGE --auto

    # Especificar un horario manual (formato ISO: YYYY-MM-DD HH:MM):
    python agregar_post.py --url "https://mi-cdn.com/reel.mp4" \
        --caption "Mira este reel" --tipo REEL --horario "2026-08-05 18:00"
"""

import argparse
import logging
from datetime import datetime

import config
import database
import analytics

logger = logging.getLogger(__name__)


def parsear_argumentos():
    parser = argparse.ArgumentParser(description="Programar un nuevo post para el Piloto Automático de Instagram.")
    parser.add_argument("--url", required=True, help="URL pública de la imagen o video a publicar.")
    parser.add_argument("--caption", default="", help="Texto/descripción de la publicación.")
    parser.add_argument("--tipo", required=True, choices=["IMAGE", "REEL"], help="Tipo de media.")

    grupo_horario = parser.add_mutually_exclusive_group(required=True)
    grupo_horario.add_argument(
        "--horario", help="Horario manual de publicación, formato 'YYYY-MM-DD HH:MM'."
    )
    grupo_horario.add_argument(
        "--auto", action="store_true",
        help="Sugerir automáticamente el horario según las horas pico de la audiencia."
    )

    return parser.parse_args()


def main():
    config.configurar_logging()
    config.validar_configuracion()
    database.inicializar_base_datos()

    args = parsear_argumentos()

    if args.auto:
        logger.info("Calculando el mejor horario según la audiencia...")
        scheduled_time = analytics.sugerir_proximo_horario_publicacion()
    else:
        scheduled_time = datetime.strptime(args.horario, "%Y-%m-%d %H:%M")

    post_id = database.crear_post(
        media_url=args.url,
        caption=args.caption,
        media_type=args.tipo,
        scheduled_time=scheduled_time,
    )

    print(f"Post programado con id={post_id} para {scheduled_time}. Estado inicial: PENDING.")


if __name__ == "__main__":
    main()
