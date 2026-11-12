# 06 · Manual de usuario

| Campo | Valor |
| :-- | :-- |
| Proyecto | Bot de Reserva de Salas UPB |
| Documento | Manual de usuario |
| Versión | 1.1 |
| Fecha | 07/11/2026 |
| Responsable | Hugo Rafael Zúñiga Daza |
| Revisado por | *(pendiente)* |
| Estado | Borrador para revisión |

> Redactado con asistencia de Claude (Anthropic).

Panel: `https://hugozuniga770.github.io/Reserva-De-Salas/`

## Parte A — Estudiantes que piden sala

### A.0 Cuándo pedir

| Momento | Qué pasa |
| :-- | :-- |
| 20:00 del día anterior | El sistema de la UPB abre las reservas del día |
| Desde las 15:30 | El bot se activa y lanza todas las solicitudes junto con la corrida principal |
| **Hasta las 18:30 del día anterior** | **Plazo**: tu solicitud entra segura en la corrida de la apertura |
| Después de las 18:30 | Se intenta, pero sin garantía (ámbar en el calendario) |
| Después de las 20:00 | Ese día ya abrió: no se asegura la reserva, solo se buscan cancelaciones (rojo en el calendario) |

La **Sala F de 12:15 a 14:15 no está disponible** (reservada por el servicio). La F en otros horarios sí.

### A.1 Pedir

1. Abre el enlace que te pasaron (termina en `#pedir`).
2. Escribe tu nombre, apellido y código **tal como figuran en UPBnet**.
3. Elige el horario y toca las salas en tu orden de preferencia (1ª, 2ª…).
4. En el calendario, toca uno o varios días. Cada día es una solicitud aparte. Los domingos no se pueden elegir. Si eliges un día marcado en ámbar o rojo, tendrás que confirmar que entiendes que no hay garantía.
5. Opcional: tu canal de **ntfy**, para recibir el resultado en el celular.
6. Marca la autorización y toca **Preparar solicitud**.
7. En cada día, toca **Enviar**. Se abre GitHub con todo listo: toca **Submit new issue**. Necesitas una cuenta de GitHub, que es gratis.
   - Si no tienes cuenta: **Copiar para WhatsApp** y mándale el texto al administrador.

Tus datos se cifran en tu teléfono antes de salir. En GitHub solo queda texto ilegible, y el bot lo borra apenas lo usa.

### A.2 Seguir el estado

En **Estado** ves tus solicitudes con su código de referencia (por ejemplo `K7X2QF`):

| Estado | Significado |
| :-- | :-- |
| Pendiente de aprobación | El administrador aún no decide. Se aprueba sola a las 18:30 |
| Aprobada | Se lanza la tarde anterior a tu día |
| En cola / En curso | El bot está trabajando en tu solicitud ahora |
| Reservada | Listo: toca «Ver resultado» para ver la sala |
| No se consiguió sala | No hubo sala libre esa noche |
| Descartada | Algún dato no era válido. Envíala de nuevo |

## Parte B — Administrador

### B.1 Primera vez

Abre el panel → **Administrar**, pega tu fine-grained token y sigue la **Guía de instalación** del panel, que tiene 8 pasos con comprobación automática:

1. Publicar el panel en GitHub Pages (carpeta `/docs`).
2. Dar permisos al token. El botón «Revisar permisos» los comprueba.
3. Crear la llave de cifrado y copiar la privada al Secret `UPB_CLAVE_PRIVADA`.
4. Verificar los Secrets (`UPB_CODIGO`, `UPB_NOMBRE`, `UPB_APELLIDO`, `NTFY_TOPIC`).
5. Opcional: cron-job.org para que el arranque sea puntual.
6. Avisos ntfy.
7. Compartir el enlace `#pedir`.
8. Prueba final sin reservar.

### B.2 Uso diario

La **barra superior** siempre muestra el estado del bot (● Vigilando, En cola, No corre o Dormido hasta…), la hora de Bolivia y tu usuario; toca el estado para ir a Inicio. En la página pública, en lugar del estado del bot, muestra el plazo o la apertura en curso.

- **Inicio**: arriba, **cómo terminó tu última corrida** (por ejemplo «Reservada ✅» o «No se liberó»). Debajo, la cuenta regresiva a las 20:00, el estado del bot, las solicitudes y tu configuración. En «Corridas recientes» cada corrida dice su resultado; la tabla completa está en [05 · Operación](05-operacion.md) §3. Botones: **Correr bot ahora**, **Probar sin reservar** y **Detener**. Si a la hora crítica el bot no corre, aparece una alerta roja con **Arrancarlo ahora**.
- **Solicitudes**: ves nombre, fecha, salas y estado de cada solicitud.
  - **Aprobar**: si es su tarde, la lanza en su propia corrida. Si no, se lanzará sola el día anterior desde las 15:30.
  - **Lanzar ahora**: solo si ya es su tarde. Si la lanzas fuera de 15:00–21:15, vigila 60 minutos buscando cancelaciones; si no consigue, la solicitud queda abierta y se relanza sola la tarde siguiente.
  - **Rechazar**: no se atenderá. Si estaba corriendo, se detiene.
  - **Quitar y borrar datos**: la cierra y borra lo cifrado.
  - **Agregar una solicitud** o **Pegar texto de WhatsApp**: para pedidos que te llegan por chat. Se crean ya aprobadas.
- **Solicitudes → Pegar de WhatsApp**: para quien no quiere usar GitHub. Esa persona prepara su solicitud en la página pública, toca «Copiar para WhatsApp» y te manda el texto; tú lo pegas entero y queda creada como pendiente (o aprobada, si marcas la casilla). Sus datos viajan cifrados también por WhatsApp; la persona sigue el estado con su referencia.
- **Ajustes**: nombre, apellido, motivo, horario, orden de salas, auto-aprobación (on/off y hora), personas por noche, solicitudes activas por persona (2 por defecto, y una por día) y pausa. Al guardar, la página pública se actualiza sola: tu primera sala en tu horario aparece como «no disponible» y la hora de auto-aprobación es el plazo que ven los solicitantes. Esto crea un commit: después corre `git pull` en tu PC antes de subir algo.

### B.3 Varios teléfonos

El token y la llave viven solo en el navegador donde los pusiste. En otro teléfono: **Administrar** → pega el token, y en Guía → paso 3 → **Importar desde otro teléfono**.
