# 02 · Requisitos

| Campo | Valor |
| :-- | :-- |
| Proyecto | Bot de Reserva de Salas UPB |
| Documento | Especificación de requisitos |
| Versión | 1.1 |
| Fecha | 07/11/2026 |
| Responsable | Hugo Rafael Zúñiga Daza |
| Revisado por | *(pendiente)* |
| Estado | Borrador para revisión |

> Redactado con asistencia de Claude (Anthropic). **[ACUERDO]** = lo pidió el responsable. **[PROPUESTA]** = lo propuso el equipo técnico y el responsable lo aceptó o no lo objetó; requiere su confirmación formal.

## 1. Requisitos funcionales

| ID | Requisito | Origen |
| :-- | :-- | :-- |
| RF-01 | Reservar automáticamente la sala del responsable en su horario (por defecto 12:15–14:15) cuando el sistema abre el día siguiente. | [ACUERDO] |
| RF-02 | No informar una reserva como hecha hasta verla en el calendario del servidor con el nombre de la persona. | [ACUERDO] |
| RF-03 | Probar salas en orden de preferencia (por defecto F → D → B → C), **solo salas de estudio**, y pasar a la siguiente si la anterior está ocupada o se perdió. | [ACUERDO] |
| RF-04 | Vigilar de cerca entre 19:00 y 21:00 BO, con ritmo máximo entre 19:45 y 20:15 BO. | [ACUERDO] |
| RF-05 | Estar corriendo a las 20:00 BO aunque GitHub retrase los arranques programados. | [ACUERDO] |
| RF-06 | Avisar al celular: vigilando, reservado, arrancó tarde y sin sala. | [ACUERDO] |
| RF-07 | Panel web para el celular, con el estilo de UPBnet y su logo: correr el bot, probar sin reservar, detener y ver el estado. | [ACUERDO] |
| RF-08 | Cambiar desde el panel el nombre, el apellido, el motivo, el horario y el orden de salas, sin tocar código. | [ACUERDO] |
| RF-09 | Pausar los arranques automáticos (feriados, vacaciones). | [PROPUESTA] |
| RF-10 | Página pública para que otros estudiantes pidan sala eligiendo uno o varios días en un calendario, con cualquier anticipación. | [ACUERDO] |
| RF-11 | El responsable aprueba, rechaza o quita solicitudes. Las pendientes se aprueban solas a una hora configurable (18:30 BO por defecto) si el responsable no decide. | [ACUERDO] |
| RF-12 | Cada solicitud se atiende en **su propia corrida aislada**: no existe una lista de usuarios, los datos son temporales y se borran tras usarse, y eliminar una solicitud no afecta a las demás. | [ACUERDO] |
| RF-13 | Cualquier persona puede ver si el bot y su solicitud están corriendo, sin ver datos personales de nadie. | [ACUERDO] |
| RF-14 | La sala favorita del responsable en su horario (por defecto Sala F, 12:15–14:15) **no está disponible** para solicitudes. La página la muestra como «reservada por el servicio», sin nombrar a nadie, y el bot la quita de cualquier solicitud. Reemplaza a la regla de prioridad de 20 s (v4.1). | [ACUERDO] |
| RF-15 | Tope de personas atendidas por noche (por defecto 4, incluido el responsable). | [PROPUESTA] |
| RF-16 | Plazos explícitos para los solicitantes: el sistema abre a las 20:00 del día anterior; el bot se activa desde las 15:30 y lanza las solicitudes junto con la corrida principal; **plazo hasta las 18:30 del día anterior**; después se intenta sin garantía; después de las 20:00 no se asegura la reserva del día siguiente (solo cancelaciones). Cuenta regresiva, marcas en el calendario y confirmación explícita para días sin garantía. | [ACUERDO] |
| RF-17 | Protección contra copias sin hacer privado el repositorio: licencia con todos los derechos reservados, y el bot y el panel solo funcionan en el repositorio y la dirección originales. | [ACUERDO] |

## 2. Requisitos no funcionales

| ID | Requisito | Origen |
| :-- | :-- | :-- |
| RNF-01 | **Ritmo acotado de consultas**: como máximo ~4/s en la corrida del responsable y ~1/s por ticket, solo en la ventana crítica. Los valores van fijos en el código. | [PROPUESTA]. El responsable pidió «miles de peticiones, cada milisegundo». Se descartó (ver D-04 en [03 · Arquitectura](03-arquitectura.md)) |
| RNF-02 | Los datos de terceros viajan y se guardan cifrados (RSA-OAEP-SHA256 + AES-256-GCM). Nada personal en títulos, comentarios, nombres de corridas ni registros públicos. | [ACUERDO] |
| RNF-03 | No existe un registro persistente de usuarios. | [ACUERDO] |
| RNF-04 | Tolerancia a red inestable: tiempo de espera de 25–30 s por petición y reintentos con espera creciente. Nunca se queda colgado esperando media hora. | [ACUERDO] |
| RNF-05 | El panel funciona con datos móviles lentos: un solo archivo, sin fuentes obligatorias y con avisos claros de error. | [PROPUESTA] |
| RNF-06 | Las pruebas automáticas corren en cada cambio (GitHub Actions). | [PROPUESTA] |
| RNF-07 | Los secretos (código, llave privada, token) nunca van en el código ni en el repositorio. | [PROPUESTA] |
| RNF-08 | El panel deja claro que es un proyecto estudiantil, no un sistema oficial de la UPB. | [PROPUESTA] |

## 3. Historias de usuario

**HU-01 — Reserva sin falsos positivos** (RF-01, RF-02)
Como responsable, quiero que el bot solo me diga «reservado» cuando la reserva exista de verdad, para no quedarme sin sala creyendo que la tengo.

- CA-01.1: Si el servidor muestra «éxito» pero la reserva no aparece en el calendario, el bot **no** la cuenta.
- CA-01.2: Si la conexión se corta al enviar, el bot verifica antes de reintentar y no envía dos veces.
- CA-01.3: Si otra persona gana la carrera, no se informa éxito.

**HU-02 — Mi sala, en mi orden** (RF-03, RF-14)
Como responsable, quiero que el bot pruebe F, luego D, B y C, para quedarme siempre con una sala de estudio.

- CA-02.1: Si F, D y B están ocupadas, reserva C.
- CA-02.2: Nunca intenta una sala de lectura.
- CA-02.3: Ninguna solicitud puede usar la sala del servicio en su horario: la página la bloquea y el bot la quita. Si era la única sala pedida, la solicitud se descarta explicando que no está disponible. La F en otro horario sí se puede pedir.

**HU-03 — Que siempre esté corriendo** (RF-04, RF-05, RF-06)
Como responsable, quiero que el bot esté vigilando a las 20:00 aunque GitHub lo retrase, y enterarme si no lo está.

- CA-03.1: Arranque cuando arranque, termina a las 21:15 BO.
- CA-03.2: Si arranca después de la apertura sin sala, avisa y la corrida queda en rojo.
- CA-03.3: El panel muestra una alerta roja con «Arrancarlo ahora» si no hay corrida entre 18:45 y 21:15.

**HU-04 — Controlar desde el celular** (RF-07, RF-08, RF-09)
Como responsable, quiero correr, probar, pausar y configurar el bot desde el teléfono.

- CA-04.1: «Correr bot ahora» lanza una corrida. Fuera de la noche vigila 60 minutos.
- CA-04.2: Los cambios de Ajustes se guardan como Variables y los usa la siguiente corrida.

**HU-05 — Pedir sala sin exponer mis datos** (RF-10, RF-12, RF-13, RNF-02)
Como estudiante, quiero pedir sala para uno o varios días y seguir su estado, sin que nadie más pueda ver mi código.

- CA-05.1: Lo que cifra el navegador solo lo descifran el bot y el panel del responsable.
- CA-05.2: Ni el título, ni el comentario de resultado, ni los registros públicos contienen nombre o código.
- CA-05.3: Al terminar, el bot borra los datos cifrados del ticket.
- CA-05.4: El estado se consulta con un código de referencia de 6 caracteres.

**HU-06 — Aprobar o que se apruebe solo** (RF-11, RF-12, RF-15)
Como responsable, quiero revisar las solicitudes. Si no llego a hacerlo, quiero que se atiendan igual.

- CA-06.1: Una pendiente no se lanza antes de la hora de auto-aprobación, y sí después.
- CA-06.2: Una rechazada nunca se lanza. Una «en curso» no se lanza dos veces.
- CA-06.3: Una solicitud con semanas de anticipación se lanza recién la tarde anterior (desde las 15:30 BO).
- CA-06.4: Eliminar una solicitud no afecta a las demás corridas.

**HU-07 — Saber hasta cuándo puedo pedir** (RF-16)
Como estudiante, quiero saber claramente hasta qué hora puedo pedir para tener garantía.

- CA-07.1: La página muestra el plazo y el tiempo que queda; pasado el plazo o la apertura, lo dice explícitamente.
- CA-07.2: El calendario marca en ámbar los días cuyo plazo ya pasó y en rojo los que ya abrieron; para elegirlos hay que aceptar que no tienen garantía.
- CA-07.3: Si una solicitud se atiende después de la apertura y no consigue sala, el cierre explica que llegó tarde.

**HU-08 — Que no se apropien del servicio** (RF-17)
Como responsable, quiero que nadie pueda copiar el servicio y hacerlo pasar por suyo, sin tener que hacer privado el repositorio.

- CA-08.1: El bot termina con el código 5 si corre en otro repositorio, y el workflow no se ejecuta fuera del original.
- CA-08.2: El panel publicado en otro dominio muestra «copia no autorizada» y no funciona.
- CA-08.3: El repositorio incluye una licencia con todos los derechos reservados.

La relación de cada criterio con su prueba automática está en [07 · Pruebas y trazabilidad](07-pruebas-y-trazabilidad.md).
