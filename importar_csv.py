import csv
import subprocess
import sys
import os

def importar_desde_csv(archivo_csv):
    print(f"Abriendo el archivo de publicaciones: {archivo_csv}...\n")
    
    if not os.path.exists(archivo_csv):
        print(f"❌ Error: No se encontró el archivo '{archivo_csv}' en esta carpeta.")
        return

    try:
        with open(archivo_csv, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            for fila_num, fila in enumerate(reader, start=2):
                # Normalizar nombres de columnas a minúsculas
                fila_clean = {str(k).lower().strip(): v for k, v in fila.items() if k}

                url = fila_clean.get('url', '').strip()
                caption = fila_clean.get('caption', '').strip()
                tipo = fila_clean.get('tipo', '').strip().upper()
                horario = fila_clean.get('horario', '').strip()

                # Convertir variaciones comunes al formato oficial
                if tipo in ['IMAGEN', 'FOTO', 'IMAGE']:
                    tipo = 'IMAGE'

                # Verificar que no falten datos
                if not all([url, caption, tipo, horario]):
                    print(f"⚠️ Faltan datos en la fila {fila_num}. Se omitirá esta línea.")
                    continue

                # Armar el comando para la terminal
                comando = [
                    "python", "agregar_post.py",
                    "--url", url,
                    "--caption", caption,
                    "--tipo", tipo,
                    "--horario", horario
                ]

                print(f"⏳ Programando post: '{caption[:20]}...' para el {horario}")
                
                # Ejecutar agregar_post.py
                resultado = subprocess.run(comando, capture_output=True, text=True)

                if resultado.returncode == 0:
                    print("✅ ¡Guardado con éxito en la base de datos!\n")
                else:
                    print(f"❌ Error al guardar (Fila {fila_num}):\n{resultado.stderr}\n")

        print("🎉 ¡Proceso de importación masiva finalizado!")

    except Exception as e:
        print(f"❌ Ocurrió un error inesperado al leer el archivo: {e}")

if __name__ == "__main__":
    importar_desde_csv("posts.csv")