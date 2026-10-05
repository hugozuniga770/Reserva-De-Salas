import subprocess
import time
import sys

# Lista de tus archivos en el orden que quieres que roten
archivos = ["reserva.py", "reserva1.py", "reserva2.py"]
minutos_espera = 1

# 280 intentos x ~1.25 minutos = ~5.8 horas (termina justo antes del límite de GitHub)
max_intentos = 280

print("Iniciando bucle de reservas escalonado...")

for i in range(max_intentos):
    script_actual = archivos[i % len(archivos)]
    print(f"\n--- INTENTO {i + 1} ---")
    print(f"Ejecutando: {script_actual}")
    
    # Ejecuta el archivo .py actual
    resultado = subprocess.run([sys.executable, script_actual])
    
    # Si la reserva tiene éxito, el código de estado será 0
    if resultado.returncode == 0:
        print(f"✅ ¡ÉXITO! {script_actual} logró asegurar la sala.")
        print("Deteniendo todos los intentos.")
        sys.exit(0) # Termina el programa y le avisa a GitHub que todo salió bien
        
    else:
        print(f"❌ {script_actual} falló o el horario aún no abre.")
        if i < max_intentos - 1:
            print(f"⏳ Esperando {minutos_espera} minutos para el siguiente intento...")
            time.sleep(minutos_espera * 60)
        else:
            print("Se alcanzó el límite de 6 horas de intentos para este turno.")
            sys.exit(1) # Le avisa a GitHub que el turno completo falló
