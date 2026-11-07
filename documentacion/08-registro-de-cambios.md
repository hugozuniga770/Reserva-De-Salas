# 08 · Registro de cambios

| Campo | Valor |
| :-- | :-- |
| Proyecto | Bot de Reserva de Salas UPB |
| Documento | Registro de cambios |
| Versión | 1.1 |
| Fecha | 07/11/2026 |
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
| C-10 | 06/11/2026 | **Corrección crítica**: `run-name` y `concurrency` del workflow van entre comillas. Sin ellas, YAML tomaba « #» como comentario y GitHub rechazaba el workflow entero (422 al aprobar un ticket; ninguna corrida podía arrancar) | Incidente del 05/11 22:54 al aprobar la primera solicitud real (#1) | `reservar.yml`, D-12 |
| C-11 | 06/11/2026 | Un ticket lanzado después de las 21:15 ya no se cierra como «sin sala» tras una sola consulta: vigila 60 min y, si no consigue, queda abierto para relanzarse | Revisión del caso #1 (aprobado a las 22:54) | RF-12, `reserva_bot.py`, panel |
| C-12 | 06/11/2026 | El panel muestra y detiene la corrida que está **corriendo**, no la que espera en cola en el mismo carril | Revisión de los 5 arranques escalonados | RF-07, panel |
| C-13 | 06/11/2026 | Guardias nuevas: prueba que lee el YAML como GitHub, actionlint en el CI, pruebas del bot completo por HTTP con las variables de Actions y un GitHub simulado que rechaza entradas inválidas | Que un error como C-10 no vuelva a llegar a producción | RNF-06 |
| C-14 | 07/11/2026 | Plazos explícitos en la página pública: recuadro «Cuándo pedir», cuenta regresiva, marcas ámbar y roja en el calendario y confirmación obligatoria para días sin garantía. El cierre de un ticket que llegó tarde lo explica | Pedido del responsable: que quede claro que hay que pedir con anticipación (plazo 18:30) y que después de las 20:00 no se asegura el día siguiente | RF-16, HU-07 |
| C-15 | 07/11/2026 | La Sala F de 12:15–14:15 (tu sala y horario) no está disponible para solicitudes: bloqueada en la página («reservada por el servicio») y en el bot. Se elimina la regla de prioridad de 20 s | Pedido del responsable, sin exponer su nombre | RF-14, D-13 |
| C-16 | 07/11/2026 | Corrección: un ticket cuyo horario ya pasó se cierra de inmediato. Antes su corrida terminaba sin cerrarlo y tu corrida lo relanzaba cada 5 minutos | Detectado por la prueba nueva de C-14 | RF-12 |
| C-17 | 07/11/2026 | Protección contra copias: `LICENSE` con todos los derechos reservados, candado de repositorio en el workflow y el bot (código de salida 5) y candado de dominio en el panel | Pedido del responsable: que no se apropien del servicio sin hacerlo privado | RF-17, D-14 |
| C-18 | 07/11/2026 | Cada corrida informa su resultado (reservada, ya la tenías, no se liberó, en progreso, pendiente, prueba, descartada, error…) como un paso «Resultado: …» en Actions. El panel lo muestra en «Corridas recientes» y destaca «Tu última corrida» en Inicio | Pedido del responsable: saber si se reservó o no, y no solo «terminó bien» | RF-07, CA-04.3, D-15 |
| C-19 | 07/11/2026 | El panel oculta las corridas fantasma de «push» del 05/11 (GitHub las crea fallidas mientras el workflow es inválido) | Aparecían como «Con error» y confundían | CA-04.5 |
| C-20 | 07/11/2026 | Barra superior rediseñada: oscura y continua con el logo, franja con los colores de las salas, pastilla de estado en vivo (vigilando, en cola, no corre, plazo, apertura), hora de Bolivia y chip de usuario. Funciona en modo claro y oscuro, en celular y escritorio | Pedido del responsable: la barra blanca con «Administrador» se veía simple | RF-07, RNF-05 |
| C-21 | 07/11/2026 | Los avisos de plazo saltan los domingos (por ejemplo, el viernes por la noche indica «para el lunes, hasta el domingo a las 18:30») | Detectado al revisar las capturas de C-20 | RF-16, SUP-04 |
