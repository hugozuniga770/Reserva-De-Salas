import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By

ESTUDIANTE = "Hugo Rafael Zúñiga Daza"
CODIGO = "95503"

# Reemplaza esto con los IDs exactos que sacaste del HTML de Atari
ID_HORARIO = "hora_1215_1415" 
ID_SALA_F = "sala_f"
ID_BOTON_CONFIRMAR = "btn_confirmar"

def cazar_sala():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    
    # Optimizaciones extremas de velocidad
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # La estrategia 'eager' hace que Selenium no espere a que carguen imágenes ni estilos pesados
    options.page_load_strategy = 'eager' 

    driver = webdriver.Chrome(options=options)

    try:
        print("Iniciando modo francotirador para Sala F (12:15 - 14:15)...")
        
        # Bucle rápido de refresco (sin cerrar el navegador)
        for intento in range(2000): 
            driver.get("https://atari.scz.upb.edu/student_reservation.php")
            
            try:
                # 1. Seleccionar el horario
                horario_btn = driver.find_element(By.ID, ID_HORARIO)
                horario_btn.click()
                
                # Pequeña pausa si el DOM necesita actualizar los colores de las salas
                time.sleep(0.3) 
                
                # 2. Buscar la Sala F
                sala_btn = driver.find_element(By.ID, ID_SALA_F)
                
                # 3. Verificar si está libre
                if "ocupado" not in sala_btn.get_attribute("class"):
                    print(f"¡SALA LIBRE DETECTADA EN EL INTENTO {intento + 1}! Disparando clic...")
                    sala_btn.click()
                    
                    # Confirmar reserva
                    driver.find_element(By.ID, ID_BOTON_CONFIRMAR).click()
                    print("✅ Reserva asegurada.")
                    return True
                else:
                    # Imprime en la misma línea para no saturar los logs de GitHub
                    print(f"\rIntento {intento + 1}: Sala F sigue ocupada...", end="", flush=True)
                    
            except Exception as e:
                print(f"\rIntento {intento + 1}: Esperando que se habilite el formulario...", end="", flush=True)

            # Espera 3 segundos antes de volver a recargar la página
            time.sleep(3)

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
