import database

# Crea todas las tablas usando el motor configurado en database.py
database.Base.metadata.create_all(bind=database.engine)

# Crea la sesión vinculada correctamente al engine
db = database.SessionLocal() # O sessionmaker configurado

# Comprueba si el usuario ya existe para no duplicarlo
existente = db.query(database.UserLogin).filter_by(email='redesgas23@gmail.com').first()
if not existente:
    nuevo_usuario = database.UserLogin(
        username='Agus',
        email='redesgas23@gmail.com',
        password='Agus2342001',
        role='admin'
    )
    db.add(nuevo_usuario)
    db.commit()
    print("¡Base de datos inicializada y usuario creado con éxito!")
else:
    print("¡La base de datos ya está lista y el usuario ya existe!")
db.close()