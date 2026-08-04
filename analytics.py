"""
Motor de inteligencia y métricas.

Se conecta con la API de Insights de Instagram para obtener la métrica
`online_followers` (cuántos seguidores están conectados, hora por hora)
y calcula las horas del día con mayor actividad, para poder sugerir
inteligentemente el horario de publicación (`scheduled_time`).
"""

import logging
from datetime import datetime, timedelta

import requests

import config

logger = logging.getLogger(__name__)


class AnalyticsError(Exception):
    """Excepción específica para errores del motor de analítica."""
    pass


def obtener_online_followers() -> dict:
    """
    Consulta el endpoint de Insights de la cuenta para obtener la métrica
    `online_followers`. Esta métrica retorna, para el período más reciente
    disponible, un mapa {hora_del_dia (0-23): cantidad_de_seguidores_online}.

    Nota: `online_followers` requiere una cuenta Business/Creator y
    permisos de `instagram_manage_insights`.
    """
    url = f"{config.GRAPH_API_BASE_URL}/{config.IG_ACCOUNT_ID}/insights"
    params = {
        "metric": "online_followers",
        "period": "lifetime",
        "access_token": config.ACCESS_TOKEN,
    }

    try:
        respuesta = requests.get(url, params=params, timeout=15)
        respuesta.raise_for_status()
    except requests.exceptions.HTTPError as error:
        logger.error("Error HTTP al consultar online_followers: %s", respuesta.text)
        raise AnalyticsError(f"Error al consultar Insights: {error}") from error
    except requests.exceptions.RequestException as error:
        logger.error("Error de conexión al consultar Insights: %s", error)
        raise AnalyticsError(f"Error de conexión con la Graph API: {error}") from error

    datos = respuesta.json()

    try:
        # La API retorna una lista en "data" -> "values", donde el último
        # elemento suele ser el dato más reciente: un mapa {hora: cantidad}.
        valores = datos["data"][0]["values"]
        mapa_horas_str = valores[-1]["value"]
    except (KeyError, IndexError) as error:
        logger.error("Formato inesperado en la respuesta de Insights: %s", datos)
        raise AnalyticsError("No se pudo interpretar la respuesta de online_followers.") from error

    # Las claves llegan como string ("0", "1", ..., "23"); se normalizan a int.
    mapa_horas = {int(hora): cantidad for hora, cantidad in mapa_horas_str.items()}
    logger.info("Se obtuvieron datos de online_followers para %d horas del día.", len(mapa_horas))
    return mapa_horas


def calcular_horas_pico(mapa_horas: dict, cantidad_horas: int = 3) -> list:
    """
    Recibe el mapa {hora: cantidad_de_seguidores_online} y retorna una
    lista con las `cantidad_horas` horas del día (0-23) de mayor actividad,
    ordenadas de mayor a menor cantidad de seguidores conectados.
    """
    if not mapa_horas:
        raise AnalyticsError("No hay datos de audiencia para calcular horas pico.")

    horas_ordenadas = sorted(mapa_horas.items(), key=lambda item: item[1], reverse=True)
    horas_pico = [hora for hora, _cantidad in horas_ordenadas[:cantidad_horas]]

    logger.info("Horas pico calculadas: %s", horas_pico)
    return horas_pico


def sugerir_proximo_horario_publicacion(cantidad_horas_pico: int = 3) -> datetime:
    """
    Determina el próximo datetime (a partir de ahora) que caiga en una
    de las horas pico de actividad de la audiencia.

    Si todas las horas pico de hoy ya pasaron, sugiere la primera hora
    pico disponible del día siguiente.
    """
    mapa_horas = obtener_online_followers()
    horas_pico = sorted(calcular_horas_pico(mapa_horas, cantidad_horas_pico))

    ahora = datetime.now()

    for hora in horas_pico:
        candidato = ahora.replace(hour=hora, minute=0, second=0, microsecond=0)
        if candidato > ahora:
            logger.info("Próximo horario sugerido: %s", candidato)
            return candidato

    # Ninguna hora pico de hoy es futura: se agenda para mañana.
    primera_hora_pico = horas_pico[0]
    candidato_manana = (ahora + timedelta(days=1)).replace(
        hour=primera_hora_pico, minute=0, second=0, microsecond=0
    )
    logger.info("Todas las horas pico de hoy ya pasaron. Próximo horario sugerido: %s", candidato_manana)
    return candidato_manana
