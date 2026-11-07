# 09 · Glosario

| Campo | Valor |
| :-- | :-- |
| Proyecto | Bot de Reserva de Salas UPB |
| Documento | Glosario y convenciones |
| Versión | 1.1 |
| Fecha | 07/11/2026 |
| Responsable | Hugo Rafael Zúñiga Daza |

> Redactado con asistencia de Claude (Anthropic).

## Marcas usadas en la documentación

| Marca | Significado |
| :-- | :-- |
| **[ACUERDO]** | Lo pidió o confirmó el responsable |
| **[PROPUESTA]** | Lo propuso el equipo técnico; requiere confirmación formal |
| **[SUPUESTO]** | Se asume a partir de evidencia indirecta; tiene un modo de verificarse |
| **[PROVISIONAL]** | Funciona en pruebas, pero falta la verificación en el entorno real |

## Términos

| Término | Definición |
| :-- | :-- |
| Apertura | Momento en que el sistema de la UPB pasa al día siguiente. Se asume a las 20:00 BO |
| Banda | Ventana de 19:00 a 21:00 BO en la que el bot consulta cada 1 s |
| BO | Hora de Bolivia (UTC−4, sin horario de verano) |
| Carril | Grupo de concurrencia de GitHub Actions. Dos corridas del mismo carril no corren a la vez; las de carriles distintos sí |
| Corrida | Una ejecución del workflow `reservar.yml` |
| Corrida aislada | La corrida de un solo ticket: solo conoce los datos de esa persona |
| Dry-run / prueba sin reservar | Corrida que hace todo menos enviar el formulario |
| Fin por reloj | La corrida termina a una hora fija (21:15 BO), sin importar cuándo arrancó |
| Latido | Aviso 🟢 de que el bot está vivo antes de la apertura |
| Llave pública / privada | Par RSA. La pública cifra las solicitudes y la privada (Secret y panel) las lee |
| Candado | Comprobación que hace que el bot y el panel solo funcionen en el repositorio y la dirección originales |
| Núcleo | Ventana de 19:45 a 20:15 BO, con el ritmo máximo |
| Plazo | Hora límite del día anterior (18:30 por defecto) para que una solicitud entre segura en la corrida de la apertura |
| Referencia | Código de 6 caracteres en el título del ticket. Permite ver el estado sin datos personales |
| Responsable / dueño | Hugo Rafael Zúñiga Daza, cuya reserva siempre corre |
| Sala del servicio | Tu primera sala en tu horario (por defecto F, 12:15–14:15). No está disponible para solicitudes |
| Ticket / solicitud | Issue de GitHub con los datos cifrados de un pedido de sala para un día |
| Verificación | Volver a leer el calendario del servidor y encontrar el nombre de la persona en ese horario |
