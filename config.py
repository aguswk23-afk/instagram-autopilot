"""
Módulo de configuración central del proyecto.

Carga las variables de entorno desde el archivo .env y expone
constantes reutilizables por el resto de los módulos, evitando
que cada archivo tenga que leer el entorno por su cuenta.
"""

import os
import logging
from dotenv import load_dotenv

# Cargamos las variables definidas en el archivo .env al entorno del proceso.
load_dotenv()

# --- Credenciales y datos de la cuenta de Instagram ---
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")

# --- Configuración de la Graph API de Meta ---
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")
GRAPH_API_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# --- Configuración de la base de datos local ---
DATABASE_PATH = os.getenv("DATABASE_PATH", "instagram_autopilot.db")

# --- Configuración del scheduler ---
# Cada cuántos minutos el ejecutor revisa la base de datos en busca de posts pendientes.
SCHEDULER_INTERVAL_MINUTES = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "5"))

# --- Configuración del polling de estado de contenedores de media ---
MEDIA_STATUS_POLL_INTERVAL_SECONDS = int(os.getenv("MEDIA_STATUS_POLL_INTERVAL_SECONDS", "10"))
MEDIA_STATUS_MAX_ATTEMPTS = int(os.getenv("MEDIA_STATUS_MAX_ATTEMPTS", "30"))  # ~5 min de espera máxima

# --- Configuración de logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "autopilot.log")


def validar_configuracion():
    """
    Valida que las variables de entorno críticas estén presentes.
    Lanza una excepción clara si falta alguna, para evitar fallos
    silenciosos más adelante en la ejecución (por ejemplo, un 401
    de la API sin contexto de por qué ocurrió).
    """
    faltantes = []
    if not ACCESS_TOKEN:
        faltantes.append("ACCESS_TOKEN")
    if not IG_ACCOUNT_ID:
        faltantes.append("IG_ACCOUNT_ID")

    if faltantes:
        raise EnvironmentError(
            f"Faltan variables de entorno obligatorias en el archivo .env: {', '.join(faltantes)}"
        )


def configurar_logging():
    """
    Configura el sistema de logging global de la aplicación.
    Escribe simultáneamente en consola y en un archivo de log,
    con un formato consistente en todos los módulos.
    """
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )
