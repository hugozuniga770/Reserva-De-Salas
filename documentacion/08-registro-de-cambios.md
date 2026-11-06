# 08 · Registro de cambios

| Campo | Valor |
| :-- | :-- |
| Proyecto | Bot de Reserva de Salas UPB |
| Documento | Registro de cambios |
| Versión | 1.0 |
| Fecha | 05/11/2026 |
| Responsable | Hugo Rafael Zúñiga Daza |
| Estado | Vigente |

> Redactado con asistencia de Claude (Anthropic). Cada cambio indica qué se cambió, por qué, y dónde se refleja.

| ID | Fecha | Cambio | Motivo | Afecta |
| :-- | :-- | :-- | :-- | :-- |
| C-01 | 23/10/2026 | Bot v2: formulario por HTTP en vez de Selenium. Verificación en el calendario antes de informar éxito | Dos falsos positivos en la v1: no leía la respuesta y cerraba el navegador justo después del clic | RF-01, RF-02, D-01, D-02 |
| C-02 | 23/10/2026 | Se eliminan `reserva_agresiva.py`, `horario_A.py` y `horario_D.py`. Datos personales a Secrets | Código duplicado y datos expuestos en el repositorio público | RNF-07 |
| C-03 | 23/10/2026 | Orden de salas F→D→B→C, solo de estudio. Ritmo 2 s / 0,25 s, fijo en el código | Pedido del responsable. Se rechaza el pedido de «una petición por milisegundo» | RF-03, RNF-01, D-04 |
| C-04 | 23/10/2026 | Banda de vigilancia 19:00–21:00 BO. Tiempos de espera cortos con reintento | Conexión móvil inestable; incertidumbre entre 19:59 y 20:00 | RF-04, RNF-04 |
| C-05 | 03/11/2026 | El responsable mueve el arranque a 18:30 BO (commit `834dba0`) | Buscar un arranque más cercano a la apertura | — |
| C-06 | 05/11/2026 | 5 arranques escalonados, fin por reloj a las 21:15, alarmas de arranque tardío, latido 🟢 y aviso ❌ | El `cron` de las 18:30 arrancó unas 4 h tarde el 03 y el 04/11. Además se corrige un error: `UPB_MAX_MINUTOS` miraba un horario que ya no existía | RF-05, RF-06, D-03 |
| C-07 | 05/11/2026 | Panel web en GitHub Pages con el estilo de UPBnet. Solicitudes de terceros cifradas | Operar desde el celular; atender a compañeros sin exponer sus datos | RF-07 a RF-11, D-05, D-09, D-10 |
| C-08 | 05/11/2026 | Una corrida aislada por ticket, en un carril de concurrencia propio. Datos temporales borrados tras usarse. Estado público por referencia. Calendario con varios días | Pedido del responsable: sin lista de usuarios, «cada corrida aislada», y que los tickets no queden «queued» detrás de su corrida | RF-10, RF-12, RF-13, D-06, D-07, D-11 |
| C-09 | 05/11/2026 | Documentación con el formato de este registro (01 a 09) y prueba del panel en Chromium dentro del CI | Entrega formal | RNF-06 |
