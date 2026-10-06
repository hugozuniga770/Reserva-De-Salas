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
VALOR_SALA_F = "8"
ID_HORARIO = "slot_b0030e1d389405aae784568ad8e26553"

def cazar_sala():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.page_load_strategy = 'eager' 

    driver = webdriver.Chrome(options=options)

    try:
        print("Iniciando modo francotirador para Sala F (12:15 - 14:15)...")
        
        for intento in range(2000): 
            driver.get("https://atari.scz.upb.edu/student_reservation.php")
            
            try:
                # 1. Seleccionar la Sala F del menú desplegable
                select_sala = Select(driver.find_element(By.ID, "roomSelect"))
                select_sala.select_by_value(VALOR_SALA_F)
                
                # Pausa mínima para que el JavaScript actualice los horarios disponibles
                time.sleep(0.3) 
                
                # 2. Buscar el radio button del horario 12:15
                horario_radio = driver.find_element(By.ID, ID_HORARIO)
                
                # 3. Verificar si NO tiene el atributo 'disabled'
                if not horario_radio.get_attribute("disabled"):
                    print(f"\n¡SALA LIBRE DETECTADA EN EL INTENTO {intento + 1}!")
                    
                    # Hacer clic en la etiqueta (label) porque el radio está oculto por CSS
                    driver.find_element(By.XPATH, f"//label[@for='{ID_HORARIO}']").click()
                    
                    # 4. Llenar rápidamente el formulario de reserva
                    driver.find_element(By.NAME, "first_name").send_keys(NOMBRE)
                    driver.find_element(By.NAME, "last_name").send_keys(APELLIDO)
                    driver.find_element(By.NAME, "code").send_keys(CODIGO)
                    driver.find_element(By.NAME, "purpose").send_keys(PROPOSITO)
                    
                    # 5. Confirmar reserva (usando la clase del botón)
                    driver.find_element(By.CSS_SELECTOR, ".btn-submit").click()
                    
                    print("✅ Reserva asegurada. Apagando francotirador.")
                    return True
                else:
                    print(f"\rIntento {intento + 1}: Sala F sigue ocupada...", end="", flush=True)
                    
            except Exception as e:
                # Si algún elemento no carga rápido, no rompe el bucle
                pass

            # Pausa breve antes de recargar la página
            time.sleep(2)

        print("\n❌ Se agotó el tiempo de búsqueda.")
        return False

    finally:
        driver.quit()

if __name__ == "__main__":
    exito = cazar_sala()
    if exito:
        sys.exit(0)
    else:
        sys.exit(1)
