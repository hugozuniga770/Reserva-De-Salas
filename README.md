# Reserva de Salas UPB — bot v2

Bot que vigila el sistema de reservas de salas de la UPB Santa Cruz
(`atari.scz.upb.edu`) y reserva automáticamente un horario cuando se libera,
**verificando siempre en el calendario del servidor que la reserva quedó a tu
nombre** antes de darla por hecha.

## Por qué la v1 daba falsos positivos

La versión con Selenium imprimía «✅ Reserva asegurada» apenas hacía clic en
*Confirmar*, sin mirar qué respondía el servidor:

1. **No verificaba nada.** Si el servidor rechazaba (otro estudiante llegó
   primero, validación, error) el bot igual decía éxito.
2. **Cerraba el navegador justo después del clic** (`return True` → `driver.quit()`),
   así que el POST podía cortarse antes de llegar al servidor.
3. **Validación HTML5 silenciosa.** Si el clic en el horario no se registraba, el
   navegador bloqueaba el envío por los campos `required` y no pasaba nada… pero
   el bot reportaba éxito.
4. `except Exception: pass` escondía todos los errores.
5. El workflow tenía `cancel-in-progress: true`: una ejecución nueva podía matar a
   la anterior en plena reserva.

## Qué hace la v2

- Lee la disponibilidad real (`const occupied`) y el calendario (`events`) del HTML.
- Envía el formulario por HTTP (sin navegador): más rápido y menos frágil.
- **Verifica** releyendo la página y buscando tu nombre en ese horario. Si no
  aparece, *no cuenta*, aunque el servidor haya mostrado «éxito».
- Si la conexión se corta al enviar, verifica igual antes de reintentar (no duplica).
- Si ya tienes la reserva, no hace nada y termina en segundos.
- Salas de respaldo en orden de preferencia, **todas "de estudio"**. Por
  defecto `8,6,15,3` (Sala F → D → B → C); cambialo con la variable
  `UPB_SALAS`. F es siempre la primera que intenta.
- No intenta horarios que ya pasaron.
- Sabe que el servidor pasa al día siguiente alrededor de las **20:00 hora
  Bolivia** (00:00 UTC), pero como a veces el servidor anda lento o
  inestable esa hora, vigila en tres niveles:
  - **19:00–21:00 BO** (la ventana que pediste): sondeo cada 1 s.
  - **19:45–20:15 BO** (núcleo, por si abre a las 19:59 o a las 20:00):
    cada 0,25 s (~4/seg).
  - El resto del día: cada 2 s, buscando por si alguien cancela.
- **Si el servidor tarda en responder, no se queda colgado esperándolo.**
  Corta la conexión a los 25-30 s y reintenta enseguida — así, si el
  servidor está lento, lo sigue consultando en vez de quedarse frízado media
  hora en una sola petición muerta. Si falla varias veces seguidas, espera
  un poco más entre reintento y reintento (hasta 8 s dentro de la ventana
  19:00–21:00, hasta 60 s fuera de ella) para no insistirle de más a un
  servidor caído.
- **A propósito no manda cientos ni miles de peticiones por segundo.** El
  servidor solo acepta una reserva por horario, así que mandar duplicados no
  mejora tus chances, sólo le pone carga a un servidor que comparte toda la
  UPB — y es el tipo de patrón que un firewall universitario o las políticas
  de uso de GitHub Actions leen como un ataque, con riesgo real de que te
  bloqueen la IP o te suspendan el workflow. 0,25 s ya es 15-20× más rápido
  que un clic humano. Estos valores están fijos en el código, no como
  variable de entorno, para que nadie los baje sin querer.
- Un detalle honesto: ningún bot puede prometer al 100% que nadie más
  reserve la F un instante antes (depende también de qué tan rápido
  reaccionen otros). Lo que sí asegura: siempre la intenta primero, siempre
  reacciona en una fracción de segundo sin que se le pase nada, y si por un
  pelo se le adelantan, cae automático a D, después B, después C.
- Si el servidor rechaza 5 veces seguidas con el mismo mensaje, se detiene y marca
  error (GitHub te manda un correo).
- Datos personales en **GitHub Secrets**, no en el código.
- Resumen claro en cada ejecución de Actions y notificación opcional al celular (ntfy).
- 28 pruebas automáticas: el falso positivo, el cambio de día, el orden de
  salas F→D→B→C de punta a punta (solo salas de estudio), los tres niveles
  de ritmo, y que nunca quede configurado como un flood.

## Configuración

1. **Settings → Secrets and variables → Actions → Secrets**:
   - `UPB_NOMBRE` = `Hugo Rafael`
   - `UPB_APELLIDO` = `Zúñiga Daza`
   - `UPB_CODIGO` = tu código
   - `NTFY_TOPIC` *(opcional)* = un nombre largo y raro, p. ej. `hugo-salas-upb-x7k2q`;
     instala la app **ntfy** y suscríbete a ese tema para recibir el aviso.
2. **Variables** (opcional): `UPB_SALAS` (def. `8`) y `UPB_HORARIO` (def. `12:15-14:15`).
3. Para probar: **Actions → Reserva Sala UPB → Run workflow** con *dry_run* marcado.

## Probar en local

```bash
pip install -r requirements.txt pytest
python -m pytest -q

# dry-run contra el sitio real
UPB_NOMBRE="Hugo Rafael" UPB_APELLIDO="Zúñiga Daza" UPB_CODIGO="xxxxx" \
UPB_DRY_RUN=1 UPB_MAX_MINUTOS=1 python reserva_bot.py
```

## Códigos de salida

| Código | Significado |
| :----: | :---------- |
| 0 | Reservado y verificado / ya la tenías / no se liberó / dry-run |
| 1 | Configuración inválida (faltan secrets, sala u horario inexistente) |
| 2 | El servidor rechazó varias veces seguidas — revisar a mano |
| 3 | No se pudo leer la página en toda la ejecución |

## Límites

El bot no puede reservar una sala que otra persona ya tiene: lo que garantiza es
que **nunca te dirá que reservó si no es verdad**, y que estará atento cuando se
libere o cuando abra el día siguiente. GitHub desactiva los workflows programados
tras 60 días sin actividad en el repo; haz un commit de vez en cuando.
