"""
Punto de entrada de la aplicación "Piloto Automático de Instagram".

Inicializa la configuración y la base de datos, y arranca el proceso
de scheduler que publicará automáticamente los posts programados.

Uso:
    python main.py
"""

import logging

import config
import database
from scheduler import iniciar_scheduler

logger = logging.getLogger(__name__)


def main():
    config.configurar_logging()
    logger.info("Iniciando Piloto Automático de Instagram...")

    config.validar_configuracion()
    database.inicializar_base_datos()

    iniciar_scheduler()


if __name__ == "__main__":
    main()
