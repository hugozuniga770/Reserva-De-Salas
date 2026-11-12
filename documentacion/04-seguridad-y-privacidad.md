# 04 · Seguridad y privacidad

| Campo | Valor |
| :-- | :-- |
| Proyecto | Bot de Reserva de Salas UPB |
| Documento | Seguridad y privacidad |
| Versión | 1.1 |
| Fecha | 07/11/2026 |
| Responsable | Hugo Rafael Zúñiga Daza |
| Revisado por | *(pendiente)* |
| Estado | Borrador para revisión |

> Redactado con asistencia de Claude (Anthropic).

## 1. Inventario de datos

| Dato | Dónde vive | Quién lo ve | Cuánto dura |
| :-- | :-- | :-- | :-- |
| Código del responsable | Secret `UPB_CODIGO` | Solo el bot (GitHub lo oculta en los registros) | Hasta que se cambie |
| Nombre y motivo del responsable | Variables o Secrets | Bot. El nombre ya es visible en el calendario de la UPB | Hasta que se cambie |
| Datos de un solicitante (nombre, código, salas, fecha) | Issue, **cifrado** | Solo el bot y el panel con la llave privada | Hasta que su corrida termina. Luego se **borran** |
| Fecha, horario, salas pedidas (letras) y referencia de un ticket | Título del issue, en claro | Cualquiera | Permanente (no es dato personal; las salas en claro permiten repartir una primera sala distinta a cada uno sin descifrar) |
| Resultado («✅ Sala D · 12:15–14:15 · fecha») | Comentario del issue | Cualquiera | Permanente (sin datos personales) |
| Token del administrador | `localStorage` del navegador del celular | Solo ese navegador | Hasta «Desconectar» |
| Llave privada | `localStorage` del celular y Secret `UPB_CLAVE_PRIVADA` | Responsable y bot | Hasta que se rote |
| Referencias de «Mis solicitudes» | `localStorage` del solicitante | Solo ese navegador | Hasta que las quite |

**[ACUERDO]** No existe ninguna lista ni registro de usuarios.

## 2. Controles

| Riesgo | Control | Dónde |
| :-- | :-- | :-- |
| Que alguien lea el código de un compañero en el repositorio público | Cifrado en el navegador (RSA-OAEP-SHA256 envuelve una llave AES-256-GCM de un solo uso) | `docs/cifrado.js`, `solicitudes.py` |
| Que los datos aparezcan en los registros públicos de Actions | `::add-mask::` antes de cualquier línea que los contenga, y nombres de corrida sin datos | `preparar_ticket()`, `run-name` |
| Que los datos queden guardados tras usarse | La corrida del ticket reemplaza el cuerpo del issue y lo cierra | `cerrar_ticket()` |
| Que el token del panel caiga en manos de un tercero | Fine-grained token limitado a este repositorio. Se guarda solo en el navegador y nunca se sube | Panel → Conectar |
| Que la página del panel ejecute contenido malicioso de un issue | Todo el texto se inserta como texto (`textContent`), nunca como HTML | `docs/index.html`, función `h()` |
| Spam de solicitudes que se auto-aprueban | Tope de personas por noche, máximo 2 solicitudes activas por persona (por autor del issue, sin descifrar) y una por día, rechazo con un toque | `UPB_MAX_PERSONAS`, `UPB_MAX_POR_PERSONA`, panel |
| Saturar el sistema de la UPB | Ritmo fijo y acotado (RNF-01). Tickets más lentos | Constantes en `reserva_bot.py` |
| Permisos excesivos de la corrida | `permissions:` mínimos: `contents: read`, `issues: write`, `actions: write` | `reservar.yml` |

## 3. Protección contra copias

Un repositorio público se puede ver y descargar: **no existe forma técnica de impedir que alguien copie el código** sin hacerlo privado. Lo que sí hace este proyecto:

| Capa | Qué hace | Dónde |
| :-- | :-- | :-- |
| Legal | Licencia con todos los derechos reservados: ver el código está permitido; copiarlo, ejecutarlo o publicarlo, no | `LICENSE`, pie del panel |
| Candado de repositorio | El workflow solo corre si `github.repository` es el original, y el bot termina con el código 5 en cualquier otro | `reservar.yml`, `REPO_AUTORIZADO` en `reserva_bot.py` |
| Candado de dominio | El panel publicado en otra dirección muestra «copia no autorizada» y no funciona | `DOMINIOS_AUTORIZADOS` en `docs/index.html` |
| El servicio no se puede llevar | Una copia nace vacía: no tiene tu código, tu llave privada, tus solicitudes ni tu enlace oficial. Los forks además tienen desactivados los horarios automáticos | Secrets, issues y Pages del repositorio original |

Si encuentras una copia publicada en GitHub, puedes pedir que la retiren con un aviso DMCA: <https://docs.github.com/es/site-policy/content-removal-policies/guide-to-submitting-a-dmca-takedown-notice>. Esto es información general, no asesoría legal.

## 4. Permisos del fine-grained token del celular

Acceso **solo** a `Reserva-De-Salas`, con estos permisos:

| Permiso | Nivel | Para qué |
| :-- | :-- | :-- |
| Actions | Read and write | Correr, probar, detener y lanzar tickets |
| Variables | Read and write | Ajustes |
| Issues | Read and write | Aprobar, rechazar y quitar solicitudes |
| Contents | Read and write | Publicar la llave pública (una vez) y la configuración pública (`servicio.json`) al guardar Ajustes |
| Metadata | Read | Obligatorio |

Para cron-job.org conviene un **token aparte con solo Actions**.

## 5. Rotación y respuesta a incidentes

- **Llave filtrada**: en Guía → paso 3, «Crear una llave nueva». Luego se actualiza el Secret `UPB_CLAVE_PRIVADA`. Las solicitudes cifradas con la llave anterior dejan de poder leerse: hay que pedirlas de nuevo.
- **Token filtrado**: revocarlo en GitHub → Developer settings, crear uno nuevo y volver a conectar el panel.
- **Celular perdido**: revocar el token. La llave privada también está en el celular, así que conviene rotarla.
- **Borrar rastros de un ticket**: en el issue, menú «edited», eliminar las revisiones anteriores.
