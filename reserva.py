from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import time

# Configuración obligatoria para servidores sin pantalla (GitHub Actions)
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

print("Iniciando navegador...")
driver = webdriver.Chrome(options=chrome_options)

try:
    # Navegar a la página
    driver.get("https://atari.scz.upb.edu/student_reservation.php")
    wait = WebDriverWait(driver, 15)
    
    print("Seleccionando la Sala F...")
    sala_select = Select(wait.until(EC.presence_of_element_located((By.ID, "roomSelect"))))
    sala_select.select_by_visible_text("Sala de estudio F") 
    time.sleep(1) # Pausa para que el JavaScript de la página actualice los horarios
    
    print("Ingresando datos del estudiante...")
    driver.find_element(By.NAME, "first_name").send_keys("Hugo Rafael")
    driver.find_element(By.NAME, "last_name").send_keys("Zuñiga Daza")
    driver.find_element(By.NAME, "code").send_keys("95503")

    print("Marcando horario 12:15 - 14:15...")
    xpath_horario = "//input[@value='12:15-14:15']/following-sibling::label"
    boton_horario = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_horario)))
    boton_horario.click()

    print("Agregando detalle de la actividad...")
    driver.find_element(By.NAME, "purpose").send_keys("Estudio grupal")

    print("Enviando formulario...")
    boton_confirmar = driver.find_element(By.XPATH, "//button[@type='submit']")
    boton_confirmar.click()
    
    print("¡Reserva ejecutada exitosamente!")
    time.sleep(2)

except Exception as e:
    print(f"Error detectado: {e}")
    # Toma una captura de pantalla si falla para que puedas ver el error en GitHub
    driver.save_screenshot("error_screenshot.png")
    raise e 

finally:
    driver.quit()
