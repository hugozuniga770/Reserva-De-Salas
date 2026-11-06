# Bot de Reserva de Salas UPB

| Campo | Valor |
| :-- | :-- |
| Proyecto | Reserva automática de salas de estudio, UPB sede Santa Cruz |
| Responsable | Hugo Rafael Zúñiga Daza |
| Versión | 3.0 |
| Fecha | 05/11/2026 |
| Estado | En pruebas: verificado contra entornos simulados; falta la verificación en el sistema real (ver §7) |
| Panel | `https://hugozuniga770.github.io/Reserva-De-Salas/` |

> Proyecto estudiantil. **No es un sistema oficial de la UPB.** Redactado con asistencia de Claude (Anthropic).

## 1. Qué hace

- **Tu reserva diaria.** Cada tarde arranca solo y espera la apertura del día siguiente (20:00 hora Bolivia). Reserva tu sala de estudio preferida (F → D → B → C) en tu horario y **solo la da por hecha cuando la ve en el calendario del servidor**.
- **Solicitudes de compañeros.** Piden sala desde una página pública, eligiendo días en un calendario. Sus datos viajan cifrados, cada solicitud se atiende en **su propia corrida aislada** y los datos se borran después de usarse.
- **Control desde el celular.** Un panel con el estilo de UPBnet permite correr, probar, detener, configurar, aprobar solicitudes y ver el estado.

## 2. Arquitectura en una mirada

```
Celular (panel, GitHub Pages) ──API──► GitHub Actions ──formulario──► Sistema de reservas UPB
Compañeros (#pedir) ──issue cifrado──► GitHub Issues ◄── la corrida aislada de cada ticket
                                                    └──► avisos ntfy
```

Detalle, diagramas y decisiones: [03 · Arquitectura](documentacion/03-arquitectura.md).

## 3. Estructura del repositorio

| Ruta | Contenido |
| :-- | :-- |
| `reserva_bot.py` | Bot: lectura, reserva, verificación, avisos y despacho de tickets |
| `solicitudes.py` | Tickets: cifrado, validación y operaciones en issues |
| `docs/` | Panel web (GitHub Pages): `index.html`, `cifrado.js` y `clave_publica.txt` (la crea el panel) |
| `.github/workflows/reservar.yml` | Horarios, carriles de concurrencia y permisos |
| `.github/workflows/tests.yml` | pytest + prueba del panel en Chromium |
| `tests/` | 60 casos de pytest y la prueba de punta a punta del panel |
| `documentacion/` | Documentación del proyecto (01 a 09) |
| `formulario.md` | Diccionario del formulario de la UPB (campos, IDs de salas y horarios) |
| `Pagina UPB/` | HTML real guardado, usado por las pruebas |

## 4. Puesta en marcha

1. **Secrets** (Settings → Secrets and variables → Actions): `UPB_CODIGO`, `UPB_NOMBRE`, `UPB_APELLIDO` y, opcional, `NTFY_TOPIC`.
2. **GitHub Pages**: Settings → Pages → rama `main`, carpeta `/docs`.
3. **Panel**: abre el enlace → *Administrar* → pega tu fine-grained token (permisos: Actions, Variables, Issues y Contents en lectura y escritura; solo este repositorio).
4. Sigue la **Guía de instalación** del panel. Ahí se crea la llave de cifrado (`UPB_CLAVE_PRIVADA`), se comprueban los permisos y se hace la prueba final.
5. Recomendado: cron-job.org para un arranque puntual (paso 5 de la guía).

Manual completo: [06 · Manual de usuario](documentacion/06-manual-de-usuario.md).

## 5. Pruebas

```bash
pip install -r requirements.txt pytest
python -m pytest -q                         # 60 casos
pip install playwright && python -m playwright install chromium
python tests/panel_e2e.py capturas          # panel en Chromium: 6 verificaciones
```

Matriz requisito ↔ prueba: [07 · Pruebas y trazabilidad](documentacion/07-pruebas-y-trazabilidad.md).

## 6. Documentación

| N.º | Documento |
| :--: | :-- |
| 01 | [Visión y alcance](documentacion/01-vision-y-alcance.md) |
| 02 | [Requisitos](documentacion/02-requisitos.md) |
| 03 | [Arquitectura y decisiones](documentacion/03-arquitectura.md) |
| 04 | [Seguridad y privacidad](documentacion/04-seguridad-y-privacidad.md) |
| 05 | [Manual de operación](documentacion/05-operacion.md) |
| 06 | [Manual de usuario](documentacion/06-manual-de-usuario.md) |
| 07 | [Pruebas y trazabilidad](documentacion/07-pruebas-y-trazabilidad.md) |
| 08 | [Registro de cambios](documentacion/08-registro-de-cambios.md) |
| 09 | [Glosario](documentacion/09-glosario.md) |

## 7. Limitaciones declaradas

- Ningún bot garantiza la sala si otra persona la reserva antes. Este maximiza las probabilidades y nunca miente sobre el resultado.
- **[SUPUESTO]** La apertura es a las 20:00 BO. Cada noche el bot registra la hora real.
- **[PROVISIONAL]** Todo se probó contra simulaciones del sistema de la UPB y de la API de GitHub. Las verificaciones en el entorno real están listadas en el documento 07, §3.
- El ritmo de consultas está acotado a propósito (máximo ~4 por segundo, solo en la ventana crítica) para no saturar el sistema de la UPB.
