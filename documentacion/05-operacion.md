# 05 · Manual de operación

| Campo | Valor |
| :-- | :-- |
| Proyecto | Bot de Reserva de Salas UPB |
| Documento | Operación diaria y respuesta a alertas |
| Versión | 1.1 |
| Fecha | 07/11/2026 |
| Responsable | Hugo Rafael Zúñiga Daza |
| Revisado por | *(pendiente)* |
| Estado | Borrador para revisión |

> Redactado con asistencia de Claude (Anthropic).

## 1. Línea de tiempo de cada día (hora Bolivia)

| Hora | Qué pasa |
| :-- | :-- |
| 15:30 | El bot se activa: los tickets del día siguiente quedan listos y tu corrida los lanza junto con la tuya |
| 15:47 · 16:53 · 17:37 · 18:11 · 18:41 | Arranques programados de tu corrida. El primero que GitHub ejecute es el que trabaja; los demás terminan en segundos |
| 17:05 · 18:05 | Disparos de cron-job.org (si está configurado) |
| 18:30 | **Plazo para los solicitantes.** Las pendientes se aprueban solas y se lanzan. Después de esta hora se intenta sin garantía |
| 19:00 | Aviso 🟢 «Bot vigilando». Empieza la banda de 1 consulta por segundo |
| 19:45–20:15 | Núcleo: ~4 consultas por segundo en tu corrida y 1 por segundo por ticket |
| 20:00 | Apertura del día siguiente **[SUPUESTO SUP-01]** |
| 21:15 | Fin de todas las corridas. Aviso ❌ si no hubo sala |

## 2. Alertas y qué hacer

| Señal | Significado | Acción |
| :-- | :-- | :-- |
| No llega el 🟢 antes de las 19:30 | El bot no está corriendo | Panel → Inicio → «Arrancarlo ahora». Si falla, reserva a mano |
| Alerta roja en el panel | No hay corrida tuya entre 18:45 y 21:15 | Igual que arriba |
| ⚠️ «Arrancó tarde» | GitHub lo arrancó después de las 20:00 | Revisa la sala a mano. Configura cron-job.org si se repite |
| Corrida en rojo con código 2 | El sistema rechazó la reserva 5 veces con el mismo mensaje | Lee el mensaje en el registro. Suele ser un dato mal escrito (código, nombre) |
| Corrida en rojo con código 3 | No se pudo leer la página en toda la corrida | Revisa si el sitio de la UPB funciona desde tu celular |
| Corrida en rojo con código 4 | Arrancó después de las 21:15 sin sala | GitHub muy atrasado. Configura cron-job.org |
| Ticket descartado | Datos ilegibles o inválidos (motivo en el comentario) | Pide al estudiante que envíe de nuevo |

## 3. Qué significa cada resultado

El panel (Inicio → «Tu última corrida» y «Corridas recientes») muestra cómo terminó cada corrida. En GitHub → Actions se ve el mismo dato como el paso «Resultado: …» de cada corrida.

| En el panel | Código | Significado | Qué hacer |
| :-- | :-- | :-- | :-- |
| En progreso: vigilando | — | La corrida está activa ahora | Nada |
| En cola | — | GitHub está por arrancarla (o espera a que termine otra tuya) | Nada |
| Reservada ✅ | `reservada` | Reservada **y verificada** en el calendario de la UPB | Nada |
| Ya la tenías | `ya-la-tenia` | La reserva ya existía; no hizo nada | Nada |
| No se liberó | `no-se-libero` | Vigiló hasta el final y ninguna sala se liberó | Reservar a mano si hace falta |
| Sin sala aún: se relanza | `pendiente` | Solicitud lanzada tarde que no consiguió todavía; queda abierta | Nada: se relanza la tarde siguiente |
| Nada que hacer | `nada` | Tu horario ya pasó y la próxima apertura cae fuera de esta corrida | Nada |
| Prueba OK | `prueba` | Prueba sin reservar | Nada |
| Solicitud descartada | `descartada` | Datos inválidos o sala no disponible (motivo en el comentario del issue) | Pedir que la envíen de nuevo |
| Solicitud ya no activa | `inactivo` | El ticket se eliminó, cerró o rechazó antes de su corrida | Nada |
| Arrancó tarde | `tarde` | GitHub la arrancó después de las 20:00 y no había sala | Configurar cron-job.org |
| Con error | `error` | Configuración, rechazo repetido de la UPB, sitio caído o copia no autorizada | Abrir «Ver» y leer el registro |

Las corridas del **05/11 marcadas con «push»** no son corridas reales. GitHub las crea, fallidas, en cada commit mientras el archivo del workflow es inválido; pasó antes de la corrección de la v4.1. El panel las oculta. Si quieres, puedes borrarlas en GitHub → Actions → cada corrida → «Delete workflow run».

## 4. Códigos de salida del bot

| Código | Significado |
| :--: | :-- |
| 0 | Reservado y verificado, ya la tenías, no se liberó, ticket terminado o prueba |
| 1 | Configuración inválida (faltan Secrets, sala u horario inexistente) |
| 2 | Rechazo repetido del sistema de reservas |
| 3 | El sitio no respondió en toda la corrida |
| 4 | Arranque tardío sin sala |
| 5 | Copia no autorizada: corrió en un repositorio que no es el original |

## 5. Tareas periódicas

| Frecuencia | Tarea |
| :-- | :-- |
| Semanal | En el panel: «Probar sin reservar». Mirar el resumen de la última noche (hora de apertura real, segundos hasta confirmar) |
| Mensual | Hacer un commit (GitHub desactiva los `cron` tras 60 días sin actividad) |
| Antes de que venza | Renovar los tokens del panel y de cron-job.org |
| Feriados y vacaciones | Ajustes → «Pausar los arranques automáticos» |

## 6. Cambios que hace el panel en el repositorio

Dos acciones del panel crean un commit en tu repositorio: crear la llave (`docs/clave_publica.txt`) y guardar Ajustes cuando cambian tu sala, horario o plazo (`docs/servicio.json`). **Antes de subir algo desde tu PC, corre `git pull`.**

## 7. Ajuste fino con datos reales

Durante la primera semana, anota en cada resumen la línea «📅 El servidor cambió a … a las HH:MM:SS». Si la apertura real no es a las 20:00, cambia `UPB_APERTURA_BO` en `reservar.yml`. La banda y el núcleo se mueven con ella.
