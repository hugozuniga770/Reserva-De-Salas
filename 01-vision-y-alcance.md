# 01 · Visión y alcance

| Campo | Valor |
| :-- | :-- |
| Proyecto | Bot de Reserva de Salas UPB (repositorio `Reserva-De-Salas`) |
| Documento | Visión y alcance |
| Versión | 1.0 |
| Fecha | 05/11/2026 |
| Responsable | Hugo Rafael Zúñiga Daza |
| Revisado por | *(pendiente)* |
| Estado | Borrador para revisión |

> Redactado con asistencia de Claude (Anthropic). Las marcas **[ACUERDO]**, **[PROPUESTA]**, **[SUPUESTO]** y **[PROVISIONAL]** se usan como en el resto de la documentación (ver [09 · Glosario](09-glosario.md)).

## 1. Problema

En la UPB (sede Santa Cruz) las salas de estudio se reservan en `atari.scz.upb.edu/student_reservation.php`. El sistema solo permite reservar **para el día de hoy**, en bloques de 2 horas, y las salas de los horarios más pedidos se agotan en minutos. **[SUPUESTO]** El sistema pasa al día siguiente a las **20:00 hora Bolivia** (00:00 UTC). Se observó en las capturas del 22/10/2026: el reloj del equipo marcaba 22/10 23:02 y la página decía «Hoy: 23/10/2026».

La primera versión del bot (Selenium) reportó **dos falsos positivos**: dijo «reserva asegurada» sin que la reserva existiera.

## 2. Objetivos

| ID | Objetivo | Medida de éxito |
| :-- | :-- | :-- |
| OBJ-01 | Que el bot nunca reporte una reserva que no existe | 0 falsos positivos. Toda reserva se confirma en el calendario del servidor |
| OBJ-02 | Conseguir la sala preferida del responsable cada día hábil | Corrida activa a las 20:00 BO todos los días. Aviso si no lo está |
| OBJ-03 | Permitir que otros estudiantes pidan sala sin exponer sus datos | Datos cifrados de punta a punta y borrados tras usarse |
| OBJ-04 | Operar todo desde el celular | Panel web con estado, acciones y ajustes |

## 3. Alcance

**Incluye:**

- La reserva diaria del responsable.
- Las solicitudes de terceros con calendario, cada una en su propia corrida.
- El panel web (público y de administración).
- Los avisos al celular.
- Las pruebas automáticas y esta documentación.

**No incluye:**

- Cancelar reservas.
- Reservar salas de lectura.
- Integrarse con sistemas oficiales de la UPB distintos de la página de reservas.
- Garantizar una sala cuando otra persona la reserva antes. **[ACUERDO]** El bot maximiza las probabilidades, no las asegura.

## 4. Interesados

| Rol | Quién | Interés |
| :-- | :-- | :-- |
| Responsable y administrador | Hugo Rafael Zúñiga Daza | Su reserva diaria. Aprueba solicitudes |
| Solicitantes | Compañeros de la UPB | Pedir sala sin instalar nada |
| Evaluador | Jefe de carrera *(nombre pendiente)* | Calidad técnica y documentación |
| Dueño del sistema de reservas | UPB (TI) | Que el bot no sature ni abuse del servicio |

## 5. Restricciones

- **Repositorio público**: los minutos de GitHub Actions son gratuitos solo en repositorios públicos. Todo lo que el bot escribe en GitHub se considera visible para cualquiera.
- **Los `cron` de GitHub no son puntuales.** Las ejecuciones programadas a las 18:30 BO arrancaron a las 22:29 y 22:37 BO (03 y 04/11/2026), según la lista de Actions.
- **El sistema de la UPB no ofrece una API.** El bot usa el mismo formulario que un estudiante.
- **No se pudo probar contra el servidor real desde el entorno de desarrollo**: el dominio no resuelve fuera de la red de la UPB. **[PROVISIONAL]** Todo se probó contra un servidor simulado construido a partir del HTML real guardado.

## 6. Supuestos

| ID | Supuesto | Cómo se verifica |
| :-- | :-- | :-- |
| SUP-01 | La apertura es a las 20:00 BO | El bot registra la hora exacta del cambio de día en el resumen de cada noche |
| SUP-02 | Los campos del formulario son `room`, `first_name`, `last_name`, `code`, `schedule` y `purpose` | Leídos del HTML guardado. Se confirma con la primera reserva real |
| SUP-03 | El calendario (`events`) muestra el nombre tal como se escribió | Visto en capturas («Hugo Rafael Zuñiga… estudio B») |
| SUP-04 | No hay reservas los domingos | El calendario del panel los bloquea. Se ajusta si resulta falso |
