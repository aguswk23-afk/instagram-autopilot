# Piloto Automático de Instagram

Aplicación local en Python que analiza las horas pico de actividad de la
audiencia de una cuenta de Instagram (vía Insights), agenda publicaciones
en una base de datos local (SQLite) y las publica automáticamente
(imágenes y Reels) usando el flujo asíncrono oficial de la Instagram
Graph API de Meta.

## Estructura del proyecto

```
instagram-autopilot/
├── .env.example        # Plantilla de variables de entorno
├── config.py           # Configuración central (lee el .env)
├── database.py         # Modelo y acceso a la base de datos (SQLite + SQLAlchemy)
├── analytics.py        # Cálculo de horas pico a partir de Insights
├── instagram_api.py    # Flujo de publicación de 3 pasos (Graph API)
├── scheduler.py        # Revisión periódica de la base de datos y publicación
├── main.py             # Punto de entrada: arranca el scheduler
├── agregar_post.py      # CLI de ejemplo para programar un nuevo post
├── requirements.txt
└── README.md
```

## Requisitos previos

- Python 3.10 o superior.
- Una cuenta de **Instagram Business o Creator**, vinculada a una página
  de Facebook.
- Una app de Meta for Developers con acceso a la **Instagram Graph API**,
  y un `ACCESS_TOKEN` de larga duración con los permisos
  `instagram_basic`, `instagram_content_publish` e
  `instagram_manage_insights`.
- El contenido a publicar (imágenes/videos) debe estar alojado en una
  **URL pública** accesible por los servidores de Meta (no rutas locales).

## Instalación

1. Clonar o descargar este proyecto y ubicarse en su carpeta.
2. Crear un entorno virtual (recomendado):
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # En Windows: venv\Scripts\activate
   ```
3. Instalar las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Copiar el archivo de variables de entorno y completarlo con tus datos:
   ```bash
   cp .env.example .env
   ```
   Editar `.env` y completar `ACCESS_TOKEN` e `IG_ACCOUNT_ID` (el ID de la
   cuenta de Instagram Business, obtenible desde el Graph API Explorer o
   consultando `/me/accounts` y luego `instagram_business_account`).

## Uso

### 1. Programar un post

Podés dejar que el sistema elija el horario óptimo automáticamente según
las horas pico de tu audiencia (`online_followers`):

```bash
python agregar_post.py --url "https://mi-cdn.com/imagen.jpg" \
    --caption "Nuevo lanzamiento 🚀" --tipo IMAGE --auto
```

O especificar un horario manual:

```bash
python agregar_post.py --url "https://mi-cdn.com/video.mp4" \
    --caption "Mira este reel" --tipo REEL --horario "2026-08-05 18:00"
```

Cada post queda guardado en la base de datos local (`instagram_autopilot.db`)
con estado `PENDING`.

### 2. Arrancar el piloto automático

```bash
python main.py
```

Esto deja un proceso corriendo que revisa la base de datos cada
`SCHEDULER_INTERVAL_MINUTES` (5 minutos por defecto). Cuando encuentra un
post `PENDING` cuya hora ya se cumplió, ejecuta el flujo de 3 pasos de
Meta (crear contenedor → esperar procesamiento → publicar) y actualiza su
estado a `PUBLISHED` o `FAILED`.

Se recomienda dejarlo corriendo en segundo plano (por ejemplo con `tmux`,
`screen`, o como servicio/tarea programada del sistema operativo).

## Estados de un post

| Estado       | Significado                                              |
|--------------|-----------------------------------------------------------|
| `PENDING`    | Programado, esperando su horario de publicación.          |
| `PROCESSING` | El scheduler lo está procesando en este momento.           |
| `PUBLISHED`  | Publicado exitosamente en Instagram.                       |
| `FAILED`     | Falló (ver columna `error_message` en la base de datos).   |

## Notas y limitaciones

- Instagram limita la cantidad de publicaciones por API a **25 por
  cuenta cada 24 horas** (rolling window).
- El `ACCESS_TOKEN` de larga duración expira cada ~60 días y debe
  renovarse manualmente o mediante un flujo de refresco aparte.
- Los Reels pueden tardar varios minutos en procesarse en los
  servidores de Meta; el `MEDIA_STATUS_MAX_ATTEMPTS` y
  `MEDIA_STATUS_POLL_INTERVAL_SECONDS` del `.env` controlan cuánto
  tiempo se espera antes de marcar el proceso como timeout.
- Los logs se guardan tanto en consola como en el archivo definido en
  `LOG_FILE` (por defecto `autopilot.log`).
