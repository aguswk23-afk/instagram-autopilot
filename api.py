"""
API Principal de Instagram Autopilot (FastAPI) - Versión con Link Directo de Mercado Pago.
Gestiona el flujo OAuth, los endpoints de autenticación SaaS, el panel de control y la programación de publicaciones.
"""

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import requests
import os
from dotenv import load_dotenv

# Cargar las variables de entorno del archivo .env
load_dotenv()

# =====================================================================
# CREDENCIALES CONFIGURADAS DESDE EL ARCHIVO .ENV
# =====================================================================
META_APP_ID = os.getenv("META_APP_ID", "1619845019762292")
META_APP_SECRET = os.getenv("META_APP_SECRET", "e57cc3ebd6acdddae5f78419f2f63c53")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")

# Link de pago directo de Mercado Pago provisto
MERCADO_PAGO_DIRECT_LINK = "https://mpago.la/1q5WGZD"

app = FastAPI(title="Instagram Autopilot API", version="1.0.0")

# Permitir que el navegador web interactúe con la API sin bloqueos de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Importamos nuestro módulo de base de datos SQLAlchemy optimizado
import database


# =====================================================================
# ENDPOINTS DE AUTENTICACIÓN Y REGISTRO SAAS (MERCADO PAGO)
# =====================================================================

class LoginRequest(BaseModel):
    usuario: str = None
    email: str = None
    password: str

class PreRegistroRequest(BaseModel):
    username: str
    email: str
    password: str


@app.post("/api/login")
def login_usuario(data: LoginRequest):
    """Valida las credenciales del usuario o correo en la base de datos local"""
    identificador = data.usuario or data.email
    if not identificador:
        raise HTTPException(status_code=422, detail="Falta el campo de usuario o correo")

    usuario = database.verificar_credenciales_usuario(identificador, data.password)
    if usuario:
        return {
            "status": "success",
            "mensaje": "Inicio de sesión exitoso",
            "user": {
                "username": usuario.username,
                "email": usuario.email,
                "role": usuario.role
            }
        }
    else:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")


@app.post("/api/pre-registro-pago")
def pre_registro_pago(data: PreRegistroRequest):
    """
    1. Recibe el correo y contraseña deseada del usuario.
    2. Retorna directamente el link de pago directo de Mercado Pago para redirigir al usuario.
    """
    try:
        if not data.email or not data.username or not data.password:
            raise HTTPException(status_code=400, detail="Faltan datos obligatorios para el registro.")

        # Opcional: Podrías registrar una pre-cuenta o almacenar temporalmente los datos si lo requieres.

        return {
            "status": "success",
            "init_point": MERCADO_PAGO_DIRECT_LINK
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# ENDPOINTS DE AUTENTICACIÓN OAUTH CON META
# =====================================================================

@app.get("/auth/login")
def auth_login():
    """Redirige al usuario al panel oficial de inicio de sesión de Meta"""
    if not META_APP_ID:
        raise HTTPException(status_code=500, detail="Falta configurar META_APP_ID en el archivo .env")
        
    fb_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth?"
        f"client_id={META_APP_ID}&redirect_uri={REDIRECT_URI}&"
        f"scope=instagram_basic,pages_show_list"
    )
    return RedirectResponse(fb_url)


@app.get("/auth/callback")
def auth_callback(code: str):
    """Intercambia el código temporal por un token de acceso y lo almacena de forma segura"""
    try:
        token_url = (
            f"https://graph.facebook.com/v18.0/oauth/access_token?"
            f"client_id={META_APP_ID}&redirect_uri={REDIRECT_URI}&"
            f"client_secret={META_APP_SECRET}&code={code}"
        )
        res = requests.get(token_url).json()
        access_token = res.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail=f"No se pudo obtener el token de acceso: {res}")

        pages_url = f"https://graph.facebook.com/v18.0/me/accounts?access_token={access_token}"
        pages_res = requests.get(pages_url).json()
        
        ig_user_id = None
        user_name = "Cuenta Comercial"
        
        for page in pages_res.get("data", []):
            page_id = page.get("id")
            page_token = page.get("access_token")
            ig_info = requests.get(
                f"https://graph.facebook.com/v18.0/{page_id}?fields=instagram_business_account,name&access_token={page_token}"
            ).json()
            
            if "instagram_business_account" in ig_info:
                ig_user_id = ig_info["instagram_business_account"]["id"]
                user_name = ig_info.get("name", "Cuenta Comercial")
                break

        database.guardar_sesion_usuario(
            ig_user_id=ig_user_id or "NO_BUSINESS_ACC",
            access_token=access_token,
            user_name=user_name
        )

        return RedirectResponse("/app/dashboard.html?login=success")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/estado")
def estado_conexion():
    """Retorna el estado de conexión actual para el widget del dashboard"""
    sesion_activa = database.obtener_sesion_activa()
    if sesion_activa and sesion_activa.access_token:
        return {
            "status": "connected", 
            "mensaje": "Cuenta de Instagram vinculada correctamente",
            "ig_account_id": sesion_activa.ig_user_id,
            "user_name": sesion_activa.user_name or "Cuenta Comercial"
        }
    else:
        raise HTTPException(status_code=400, detail="No hay ninguna cuenta vinculada en la base de datos.")


# =====================================================================
# GESTIÓN DE POSTS
# =====================================================================

@app.get("/posts")
def listar_posts():
    """Retorna la lista completa de publicaciones"""
    try:
        posts = database.obtener_todos_los_posts()
        posts_dicts = [
            {
                "id": p.id,
                "url": p.media_url,
                "media_url": p.media_url,
                "caption": p.caption,
                "tipo": p.media_type,
                "media_type": p.media_type,
                "horario": p.scheduled_time.strftime("%Y-%m-%d %H:%M") if p.scheduled_time else "Sin fecha",
                "scheduled_time": p.scheduled_time.isoformat() if p.scheduled_time else None,
                "status": p.status,
                "estado": p.status,
                "ig_container_id": p.ig_container_id,
                "ig_media_id": p.ig_media_id,
                "error_message": p.error_message
            }
            for p in posts
        ]
        return {"status": "success", "data": posts_dicts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PostRequest(BaseModel):
    url: str
    caption: str
    tipo: str
    horario: str


@app.post("/posts/crear")
def crear_post(post: PostRequest):
    """Ejecuta el script externo para programar un post unitario"""
    comando = [
        "python", "agregar_post.py",
        "--url", post.url,
        "--caption", post.caption,
        "--tipo", post.tipo.upper(),
        "--horario", post.horario
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode == 0:
        return {"status": "success", "mensaje": "Post programado con éxito"}
    else:
        raise HTTPException(status_code=400, detail=resultado.stderr)


@app.post("/posts/importar-csv")
def importar_csv():
    """Ejecuta la sincronización masiva desde fuentes externas o CSV"""
    resultado = subprocess.run(["python", "importar_csv.py"], capture_output=True, text=True)
    if resultado.returncode == 0:
        return {"status": "success", "output": resultado.stdout}
    else:
        raise HTTPException(status_code=500, detail=resultado.stderr)


# =====================================================================
# RUTA RAÍZ, LOGIN HTML Y MONTAJE ESTÁTICO
# =====================================================================

@app.get("/", response_class=HTMLResponse)
def home():
    """Sirve la página de bienvenida y pasarela de suscripción"""
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Bienvenido a Instagram Autopilot API</h1>"

@app.get("/login.html", response_class=HTMLResponse)
def login_page():
    """Sirve explícitamente la página de inicio de sesión"""
    if os.path.exists("login.html"):
        return FileResponse("login.html")
    raise HTTPException(status_code=404, detail="Archivo login.html no encontrado en el directorio.")

# Monta el resto de los archivos estáticos bajo la ruta /app
app.mount("/app", StaticFiles(directory=".", html=True), name="static")