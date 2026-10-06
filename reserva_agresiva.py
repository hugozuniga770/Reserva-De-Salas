import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

# Tus datos 
NOMBRE = "Hugo Rafael"
APELLIDO = "Zúñiga Daza"
CODIGO = "95503"
PROPOSITO = "Estudio académico"

# IDs extraídos del código fuente de Atari
VALOR_SALA_F = "15"  # Esto se mantiene igual para la Sala F
ID_HORARIO = "slot_94b8b48865360042a741a450c6441be0"  # ¡Este es el ID exacto para las 07:45 - 09:45!

# Configuración del relevo temporal
TIEMPO_INICIO = time.time()
# 2 horas (7200 segundos) menos 5 minutos (300 segundos) de margen de seguridad
LIMITE_TIEMPO_SEGUNDOS = 6900 

def cazar_sala():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.page_load_strategy = 'eager' 

    driver = webdriver.Chrome(options=options)
    intento = 1

    try:
        print("Iniciando modo francotirador para Sala F (12:15 - 14:15)...")
        print("Este turno correrá por exactamente 1 hora y 55 minutos.")
        
        # El bucle correrá MIENTRAS no se alcance el límite de tiempo
        while (time.time() - TIEMPO_INICIO) < LIMITE_TIEMPO_SEGUNDOS:
            driver.get("https://atari.scz.upb.edu/student_reservation.php")
            
            try:
                # 1. Seleccionar la Sala F
                select_sala = Select(driver.find_element(By.ID, "roomSelect"))
                select_sala.select_by_value(VALOR_SALA_F)
                
                time.sleep(0.3) 
                
                # 2. Revisar el horario de las 12:15
                horario_radio = driver.find_element(By.ID, ID_HORARIO)
                
                # 3. Si se libera, ataca
                if not horario_radio.get_attribute("disabled"):
                    print(f"\n¡SALA LIBRE DETECTADA EN EL INTENTO {intento}!")
                    
                    driver.find_element(By.XPATH, f"//label[@for='{ID_HORARIO}']").click()
                    
                    driver.find_element(By.NAME, "first_name").send_keys(NOMBRE)
                    driver.find_element(By.NAME, "last_name").send_keys(APELLIDO)
                    driver.find_element(By.NAME, "code").send_keys(CODIGO)
                    driver.find_element(By.NAME, "purpose").send_keys(PROPOSITO)
                    
                    driver.find_element(By.CSS_SELECTOR, ".btn-submit").click()
                    
                    print("✅ Reserva asegurada. Apagando francotirador definitivamente.")
                    return True
                else:
                    print(f"\rIntento {intento}: Sala F sigue ocupada... (Tiempo activo: {int(time.time() - TIEMPO_INICIO)}s)", end="", flush=True)
                    
            except Exception:
                pass # Ignora errores de carga y sigue intentando

            intento += 1
            time.sleep(2)

        print("\n⏳ Tiempo de turno agotado. Apagando para permitir el inicio del siguiente bot de GitHub.")
        return False

    finally:
        driver.quit()

if __name__ == "__main__":
    exito = cazar_sala()
    # Si tiene éxito (True), devuelve 0. Si se le acaba el tiempo (False), devuelve 0 para no marcar error en GitHub.
    sys.exit(0)
