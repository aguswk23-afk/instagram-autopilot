"""
Módulo de acceso a datos (Data Access Layer) - Versión con Nombre de Usuario y Contraseña.

Implementa la persistencia local usando SQLAlchemy sobre SQLite.
Define el modelo `Post`, el modelo `UserSession` (Instagram)
y el modelo `UserLogin` (Control de acceso de usuarios/SaaS).
"""

import logging
from datetime import datetime
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

import config

logger = logging.getLogger(__name__)

Base = declarative_base()


class PostStatus:
    """Constantes de estado, para evitar strings "mágicos" repartidos por el código."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class MediaType:
    """Tipos de media soportados por el sistema."""
    IMAGE = "IMAGE"
    REEL = "REEL"


class Post(Base):
    """Representa una publicación programada en la base de datos local."""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_url = Column(String, nullable=False)           # Ruta local o URL pública del archivo
    caption = Column(Text, nullable=True)                 # Texto/descripción de la publicación
    media_type = Column(String, nullable=False)           # IMAGE o REEL
    scheduled_time = Column(DateTime, nullable=False)     # Fecha/hora en la que debe publicarse (UTC)
    status = Column(String, nullable=False, default=PostStatus.PENDING)

    # Campos de auditoría / trazabilidad del proceso de publicación
    ig_container_id = Column(String, nullable=True)       # ID del contenedor de media en Meta
    ig_media_id = Column(String, nullable=True)            # ID final de la publicación ya publicada
    error_message = Column(Text, nullable=True)             # Último error registrado, si lo hubo

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Post id={self.id} tipo={self.media_type} estado={self.status} hora={self.scheduled_time}>"


class UserSession(Base):
    """Almacena la sesión y los tokens de la cuenta de Instagram vinculada."""

    __tablename__ = "user_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String, nullable=True, default="Cuenta Comercial") # Nombre de usuario o perfil de Meta
    ig_user_id = Column(String, nullable=False)                          # ID de la cuenta comercial de Instagram
    access_token = Column(Text, nullable=False)                          # Token de acceso de larga duración OAuth
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserSession id={self.id} user_name={self.user_name} ig_user_id={self.ig_user_id}>"


class UserLogin(Base):
    """Almacena las credenciales de acceso (SaaS Login) permitiendo iniciar sesión por usuario o correo."""

    __tablename__ = "user_login"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False) # Nombre de usuario único (ej: Agus)
    email = Column(String, unique=True, nullable=True)     # Correo opcional
    password = Column(String, nullable=False)              # Contraseña en texto plano para entorno local
    role = Column(String, default="admin")                 # "admin" para acceso total al sistema
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserLogin username={self.username} role={self.role}>"


# --- Engine y fábrica de sesiones ---
engine = create_engine(f"sqlite:///{config.DATABASE_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def inicializar_base_datos():
    """
    Crea las tablas en la base de datos si no existen todavía.
    Debe llamarse una única vez al iniciar la aplicación.
    """
    Base.metadata.create_all(engine)
    logger.info("Base de datos inicializada correctamente en '%s'.", config.DATABASE_PATH)
    
    # Crear tu cuenta de administrador personal por defecto con usuario "Agus"
    with obtener_sesion() as sesion:
        admin_existente = sesion.query(UserLogin).filter(UserLogin.username == "Agus").first()
        if not admin_existente:
            admin_inicial = UserLogin(
                username="Agus",
                email="Redgas23@gmail.com",
                password="Agus2342001",
                role="admin"
            )
            sesion.add(admin_inicial)
            logger.info("Usuario administrador personal creado (Usuario: Agus).")


@contextmanager
def obtener_sesion():
    """
    Context manager que entrega una sesión de SQLAlchemy y garantiza
    su cierre (con rollback automático en caso de error).
    """
    sesion = SessionLocal()
    try:
        yield sesion
        sesion.commit()
    except Exception:
        sesion.rollback()
        logger.exception("Error en la transacción de base de datos. Se ejecutó rollback.")
        raise
    finally:
        sesion.close()


def crear_post(media_url: str, caption: str, media_type: str, scheduled_time: datetime) -> int:
    """Inserta una nueva publicación programada en estado PENDING."""
    with obtener_sesion() as sesion:
        nuevo_post = Post(
            media_url=media_url,
            caption=caption,
            media_type=media_type,
            scheduled_time=scheduled_time,
            status=PostStatus.PENDING,
        )
        sesion.add(nuevo_post)
        sesion.flush()
        logger.info("Post creado con id=%s, programado para %s.", nuevo_post.id, scheduled_time)
        return nuevo_post.id


def obtener_posts_pendientes_listos(ahora: datetime = None):
    """Retorna todos los posts en estado PENDING cuya hora programada ya se cumplió."""
    ahora = ahora or datetime.utcnow()
    with obtener_sesion() as sesion:
        posts = (
            sesion.query(Post)
            .filter(Post.status == PostStatus.PENDING)
            .filter(Post.scheduled_time <= ahora)
            .order_by(Post.scheduled_time.asc())
            .all()
        )
        for post in posts:
            sesion.expunge(post)
        return posts


def actualizar_estado_post(post_id: int, nuevo_estado: str, error_message: str = None,
                            ig_container_id: str = None, ig_media_id: str = None):
    """Actualiza el estado de un post y sus campos relacionados."""
    with obtener_sesion() as sesion:
        post = sesion.query(Post).filter(Post.id == post_id).first()
        if not post:
            logger.warning("Se intentó actualizar un post inexistente (id=%s).", post_id)
            return

        post.status = nuevo_estado
        if error_message is not None:
            post.error_message = error_message
        if ig_container_id is not None:
            post.ig_container_id = ig_container_id
        if ig_media_id is not None:
            post.ig_media_id = ig_media_id
        post.updated_at = datetime.utcnow()

        logger.info("Post id=%s actualizado a estado '%s'.", post_id, nuevo_estado)


def obtener_todos_los_posts():
    """Retorna todos los posts registrados, ordenados por hora programada."""
    with obtener_sesion() as sesion:
        posts = sesion.query(Post).order_by(Post.scheduled_time.asc()).all()
        for post in posts:
            sesion.expunge(post)
        return posts


# --- Funciones de gestión de sesión y cuenta de Instagram ---

def guardar_sesion_usuario(ig_user_id: str, access_token: str, user_name: str = None):
    """
    Guarda o reemplaza la sesión activa de Instagram en la base de datos local.
    Si el nombre de usuario no viene especificado o es genérico, mantiene un estándar limpio.
    """
    with obtener_sesion() as sesion:
        sesion.query(UserSession).delete()
        
        nombre_final = user_name if user_name and user_name.strip() else "Cuenta Comercial"
        
        nueva_sesion = UserSession(
            user_name=nombre_final,
            ig_user_id=ig_user_id,
            access_token=access_token
        )
        sesion.add(nueva_sesion)
        logger.info("Sesión de Instagram guardada con éxito para usuario: '%s' (ig_user_id=%s).", nombre_final, ig_user_id)


def obtener_sesion_activa():
    """
    Retorna la sesión de usuario activa (token, nombre e ID de Instagram) 
    para ser utilizada al momento de realizar publicaciones en la API de Meta.
    """
    with obtener_sesion() as sesion:
        user_session = sesion.query(UserSession).first()
        if user_session:
            sesion.expunge(user_session)
        return user_session


# --- Funciones de autenticación de usuarios (Login SaaS) ---

def verificar_credenciales_usuario(identificador: str, password: str):
    """Verifica si el usuario (o correo) y la contraseña coinciden con un registro válido."""
    with obtener_sesion() as sesion:
        # Permite buscar tanto por nombre de usuario ("Agus") como por correo electrónico
        usuario = sesion.query(UserLogin).filter(
            ((UserLogin.username == identificador) | (UserLogin.email == identificador)) & 
            (UserLogin.password == password)
        ).first()
        
        if usuario:
            sesion.expunge(usuario)
            return usuario
        return None


def registrar_usuario(username: str, password: str, email: str = None, role: str = "client"):
    """Registra un nuevo usuario en la base de datos."""
    with obtener_sesion() as sesion:
        existe = sesion.query(UserLogin).filter(UserLogin.username == username).first()
        if existe:
            return False  # El usuario ya existe
        
        nuevo_usuario = UserLogin(username=username, email=email, password=password, role=role)
        sesion.add(nuevo_usuario)
        logger.info("Nuevo usuario registrado: %s", username)
        return True