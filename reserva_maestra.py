import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 1. Tus datos inamovibles (No los alteres para evitar problemas con la UPB)
ESTUDIANTE = "Hugo Rafael Zúñiga Daza"
CODIGO = "95503"

# 2. Configura tu orden de prioridad (El bot intentará en este orden exacto)
# Añade aquí los IDs o Values exactos de los horarios en el HTML
horarios_prioridad = ["hora_1900_2100", "hora_1215_1415", "hora_1415_1615"] 

# Añade aquí los IDs o Values exactos de las salas en el HTML
salas_prioridad = ["sala_1", "sala_2", "sala_3", "sala_4", "sala_5"]

def buscar_reserva():
    # Configuración de Selenium (Asegúrate de usar opciones headless para GitHub Actions)
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get("https://atari.scz.upb.edu/student_reservation.php")
        
        # Llenar datos de estudiante (Solo se hace una vez)
        # driver.find_element(By.ID, "input_codigo").send_keys(CODIGO)
        # ...
        
        # 3. Bucle de Cascada: Horarios -> Salas
        for horario in horarios_prioridad:
            print(f"\nBuscando disponibilidad en el bloque: {horario}")
            
            # Seleccionar el horario en el formulario
            # driver.find_element(By.ID, horario).click()
            time.sleep(1) # Pequeña pausa para que el DOM actualice si es necesario
            
            for sala in salas_prioridad:
                print(f"  -> Revisando {sala}...")
                
                try:
                    # Intenta seleccionar la sala
                    boton_sala = driver.find_element(By.ID, sala)
                    
                    # Lógica para verificar si está disponible (ej. si no tiene la clase 'ocupado')
                    if "ocupado" not in boton_sala.get_attribute("class"):
                        boton_sala.click()
                        
                        # Clic en el botón final de reservar
                        # driver.find_element(By.ID, "btn_confirmar").click()
                        
                        print(f"✅ ¡ÉXITO! Reserva confirmada en {sala} para el bloque {horario}.")
                        return True # Retorna éxito y sale de la función
                    else:
                        print(f"  -> {sala} ocupada.")
                        
                except Exception:
                    print(f"  -> Error o {sala} no encontrada, pasando a la siguiente...")
                    continue # Si falla, sigue con la siguiente sala
                    
        print("\n❌ Ninguna sala disponible en los horarios solicitados.")
        return False

    finally:
        driver.quit()

if __name__ == "__main__":
    exito = buscar_reserva()
    if exito:
        sys.exit(0) # Le dice a bucle.py que detenga los intentos
    else:
        sys.exit(1) # Le dice a bucle.py que espere 5 minutos y vuelva a correr todo
