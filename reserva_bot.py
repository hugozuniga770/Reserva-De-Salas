#!/usr/bin/env python3
"""
Bot de reserva de salas UPB (atari.scz.upb.edu) — versión 2.

Diferencias clave con la versión anterior (Selenium):
  * Habla directo con el servidor (HTTP), sin navegador: más rápido y sin
    problemas de carga de página.
  * NUNCA declara éxito sin VERIFICAR: después de enviar el formulario vuelve a
    descargar la página y busca la reserva con tu nombre en el calendario.
    Si no aparece, no cuenta como reservada (esto elimina el falso positivo).
  * Lee los mensajes del servidor (alert-success / alert-danger) y los muestra.
  * Si ya tienes la reserva, no hace nada más (no gasta minutos ni carga el sitio).
  * Entiende que el servidor cambia de día alrededor de las 20:00 hora Bolivia
    (00:00 UTC). Vigila de cerca una banda ancha 19:00–21:00 BO (por si el
    servidor anda lento o inestable ese rato) y, dentro de ella, un núcleo
    19:45–20:15 BO a ritmo máximo, por si abre justo a las 19:59 o a las 20:00.
  * Datos personales vía variables de entorno (GitHub Secrets), no en el código.
  * El ritmo de peticiones (2 s normal / 1 s en la banda / 0.25 s en el núcleo)
    es fijo en el código a propósito y NO es configurable por variable de
    entorno: no tiene sentido técnico mandar más de una reserva por horario
    libre (el servidor solo acepta una) y un ritmo mucho más alto es
    indistinguible de un ataque de denegación de servicio contra un servidor
    compartido con el resto de la UPB.
  * Si el servidor tarda o no responde, NO espera media hora colgado de una
    sola petición: corta a los 25-30 s y reintenta enseguida (más rápido y
    más confiable que quedarse pegado esperando una conexión que quizás nunca
    vuelva).

Variables de entorno:
  UPB_NOMBRE, UPB_APELLIDO, UPB_CODIGO   (obligatorias)
  UPB_SALAS        IDs separados por coma, en orden de preferencia — todas
                    "de estudio" (def. "8,6,15,3" = Sala F, D, B, C)
  UPB_HORARIO      p. ej. "12:15-14:15" (def.)
  UPB_PROPOSITO    texto de la actividad (def. "Estudio académico")
  UPB_HASTA_BO     hora Bolivia en que termina la ejecución (def. "21:15"). Así no
                    importa a qué hora arranque GitHub: el bot espera solo hasta la
                    apertura y se queda hasta esta hora. Vacío = sin límite por reloj.
  UPB_MAX_MINUTOS  tope de seguridad de duración (def. 340; GitHub corta a los 360)
  UPB_APERTURA_BO  hora Bolivia en que el servidor abre el día siguiente (def. "20:00")
  UPB_DRY_RUN      "1" = no envía nada, sólo dice qué haría
  UPB_AUTO_APROBAR "1" = las solicitudes pendientes se aprueban solas (def. "1")
  UPB_AUTO_APROBAR_BO  hora Bolivia de la auto-aprobación (def. "18:30")
  UPB_MAX_PERSONAS tope de personas por noche, contándote a ti (def. 4)
  UPB_CLAVE_PRIVADA, UPB_GH_TOKEN, UPB_REPO  para leer solicitudes cifradas (ver solicitudes.py)
  NTFY_TOPIC       opcional: tema de ntfy.sh para recibir una notificación al celular

Códigos de salida:
  0  reservado / ya lo tenías / no se liberó en esta ejecución / dry-run
  1  configuración inválida
  2  el servidor rechazó la reserva varias veces seguidas (revisar a mano)
  3  no se pudo leer la página en toda la ejecución
"""
from __future__ import annotations

import html as html_lib
import json
import os
import random
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import requests

VERSION = "2.0"
URL_DEFECTO = "https://atari.scz.upb.edu/student_reservation.php"
BO_TZ = timezone(timedelta(hours=-4), "BOT")  # Bolivia: UTC-4 todo el año, sin horario de verano

EXIT_OK, EXIT_CONFIG, EXIT_RECHAZOS, EXIT_SITIO, EXIT_TARDE = 0, 1, 2, 3, 4
MARCADOR_TICKET = "<!-- reserva-upb:v1 -->"
# Corridas de tickets: más suaves que la tuya, para no multiplicar la carga y que tú llegues primero.
RITMO_TICKET = {"intervalo": 4.0, "intervalo_medio": 2.0, "intervalo_rafaga": 1.0}
PRIORIDAD_DUENIO_SEG = 20  # los tickets no tocan tu sala favorita en los primeros 20 s tras la apertura


# ───────────────────────────── utilidades ──────────────────────────────

def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples: 'Zúñiga' == 'Zuñiga' == 'zuniga'."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def limpiar_html(fragmento: str) -> str:
    sin_tags = re.sub(r"<[^>]+>", " ", fragmento)
    return re.sub(r"\s+", " ", html_lib.unescape(sin_tags)).strip()


def normalizar_horario(texto: str) -> str:
    """'07:45 – 09:45', '7:45-9:45' → '7:45-9:45' (formato exacto que usa el servidor)."""
    horas = re.findall(r"(\d{1,2}):(\d{2})", texto or "")
    if len(horas) != 2:
        raise ValueError(f"Horario inválido: {texto!r} (usa algo como 12:15-14:15)")
    return "-".join(f"{int(h)}:{m}" for h, m in horas)


def hora_fin(horario: str) -> tuple[int, int]:
    h, m = horario.split("-")[1].split(":")
    return int(h), int(m)


def log(msg: str) -> None:
    ahora = datetime.now(BO_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ahora} BO] {msg}", flush=True)


# ───────────────────────────── configuración ───────────────────────────
#
# intervalo / intervalo_medio / intervalo_rafaga / intervalo_espera son
# constantes de código a propósito, NO variables de entorno: así nadie (ni
# por error, ni "para que sea más rápido") las sube a un ritmo que tumbe
# atari.scz.upb.edu para el resto de la UPB o que GitHub/la universidad
# interpreten como un ataque.
#
#   intervalo         2.0 s  sondeo normal, mientras tus salas están ocupadas
#   intervalo_medio   1.0 s  banda ancha 19:00–21:00 BO (servidor puede andar
#                     lento/inestable esa hora; vigilamos más de cerca)
#   intervalo_rafaga  0.25 s núcleo 19:45–20:15 BO: ~4 peticiones/seg, 15-20×
#                     más rápido que un clic humano — ventaja enorme sin
#                     acercarse a un flood
#   intervalo_espera  30.0 s  cuando no hay nada que hacer hasta la banda

@dataclass
class Config:
    nombre: str
    apellido: str
    codigo: str
    salas: list[str]
    horario: str
    proposito: str = "Estudio académico"
    url: str = URL_DEFECTO
    max_segundos: float = 340 * 60
    intervalo: float = 2.0            # buscando una sala que se libere
    intervalo_medio: float = 1.0      # banda ancha alrededor de la apertura
    intervalo_rafaga: float = 0.25    # núcleo de la apertura del día siguiente
    intervalo_espera: float = 30.0    # cuando ya no hay nada que hacer hasta la banda
    pausa_verificacion: float = 2.0
    apertura_bo: str = "20:00"
    hasta_bo: str = "21:15"
    dry_run: bool = False
    max_rechazos: int = 5
    ntfy_topic: str = ""
    auto_aprobar: bool = True
    auto_aprobar_bo: str = "18:30"
    max_personas: int = 4
    reloj: Callable[[], datetime] = field(default=lambda: datetime.now(BO_TZ))
    dormir: Callable[[float], None] = time.sleep

    @property
    def clave_nombre(self) -> str:
        """Lo que buscamos al inicio del título del evento: nombre + primer apellido."""
        primer_apellido = self.apellido.split()[0] if self.apellido.split() else ""
        return normalizar(f"{self.nombre} {primer_apellido}")

    @property
    def codigo_oculto(self) -> str:
        return self.codigo[:2] + "*" * max(0, len(self.codigo) - 2)

    @classmethod
    def desde_entorno(cls) -> "Config":
        faltan = [v for v in ("UPB_NOMBRE", "UPB_APELLIDO", "UPB_CODIGO") if not os.getenv(v, "").strip()]
        if faltan:
            raise ValueError("Faltan variables: " + ", ".join(faltan) + " (configúralas como GitHub Secrets)")
        # Por defecto: F, D, B, C — tu orden, y las cuatro son "de estudio".
        # (No existe "Sala de estudio A", solo "Sala de lectura A" — la dejé
        # afuera porque pediste que el respaldo sea siempre sala de estudio.)
        salas = [s.strip() for s in os.getenv("UPB_SALAS", "8,6,15,3").split(",") if s.strip()]
        if not salas or not all(s.isdigit() for s in salas):
            raise ValueError("UPB_SALAS debe ser una lista de IDs numéricos, p. ej. '8' o '8,9,14'")
        apertura = os.getenv("UPB_APERTURA_BO", "20:00").strip()
        if not re.fullmatch(r"\d{1,2}:\d{2}", apertura):
            raise ValueError("UPB_APERTURA_BO debe tener formato HH:MM")
        hasta = os.getenv("UPB_HASTA_BO", "21:15").strip()
        if hasta and not re.fullmatch(r"\d{1,2}:\d{2}", hasta):
            raise ValueError("UPB_HASTA_BO debe tener formato HH:MM (o vacío)")
        if not re.fullmatch(r"\d{1,2}:\d{2}", os.getenv("UPB_AUTO_APROBAR_BO", "18:30").strip() or "18:30"):
            raise ValueError("UPB_AUTO_APROBAR_BO debe tener formato HH:MM")
        return cls(
            nombre=os.environ["UPB_NOMBRE"].strip(),
            apellido=os.environ["UPB_APELLIDO"].strip(),
            codigo=os.environ["UPB_CODIGO"].strip(),
            salas=salas,
            horario=normalizar_horario(os.getenv("UPB_HORARIO", "12:15-14:15")),
            proposito=os.getenv("UPB_PROPOSITO", "Estudio académico").strip() or "Estudio académico",
            url=os.getenv("UPB_URL", URL_DEFECTO).strip(),
            max_segundos=float(os.getenv("UPB_MAX_MINUTOS", "340") or "340") * 60,
            apertura_bo=apertura,
            hasta_bo=hasta,
            dry_run=os.getenv("UPB_DRY_RUN", "0").strip().lower() in ("1", "true", "si", "sí", "yes"),
            ntfy_topic=os.getenv("NTFY_TOPIC", "").strip(),
            auto_aprobar=os.getenv("UPB_AUTO_APROBAR", "1").strip().lower() in ("1", "true", "si", "sí", "yes"),
            auto_aprobar_bo=(os.getenv("UPB_AUTO_APROBAR_BO", "18:30").strip() or "18:30"),
            max_personas=max(1, int(os.getenv("UPB_MAX_PERSONAS", "4").strip() or "4")),
        )


@dataclass
class Persona:
    """Alguien para quien el bot reserva: tú (dueño) o una solicitud aprobada."""
    nombre: str
    apellido: str
    codigo: str
    salas: list[str]
    horario: str
    proposito: str
    etiqueta: str                 # nombre seguro para logs públicos ("tú", "solicitud #12")
    es_duenio: bool = False
    fecha: date | None = None     # fecha de uso pedida; None = la que esté abierta
    ntfy: str = ""
    issue: int | None = None
    aprobada: bool = True
    # estado durante la ejecución
    hecha_en: date | None = None
    reservada_aqui: bool = False
    cerrada: bool = False
    ultimo_rechazo: str = ""
    rechazos_iguales: int = 0

    @property
    def clave_nombre(self) -> str:
        primer_apellido = self.apellido.split()[0] if self.apellido.split() else ""
        return normalizar(f"{self.nombre} {primer_apellido}")


# ───────────────────────────── lectura de la página ────────────────────

class PaginaInvalida(Exception):
    """La página no tiene la estructura esperada. Nunca se asume 'libre' en este caso."""


@dataclass
class Pagina:
    hoy: date | None
    salas: dict[str, str]
    horarios: list[str]
    ocupado: dict[str, dict[str, bool]]
    eventos: list[dict]
    alertas: list[tuple[str, str]]


def _json_despues_de(texto: str, patron: str):
    m = re.search(patron, texto)
    if not m:
        return None
    try:
        valor, _ = json.JSONDecoder().raw_decode(texto, m.end())
    except json.JSONDecodeError as e:
        raise PaginaInvalida(f"JSON ilegible después de {patron!r}: {e}") from e
    return valor


def leer_alertas(texto: str) -> list[tuple[str, str]]:
    alertas = []
    for m in re.finditer(r'class="[^"]*\balert-(success|danger|warning|info)\b[^"]*"[^>]*>(.*?)</div>', texto, re.S):
        mensaje = limpiar_html(m.group(2))
        if mensaje:
            alertas.append((m.group(1), mensaje))
    return alertas


def parsear(texto: str) -> Pagina:
    salas = {m.group(1): limpiar_html(m.group(2))
             for m in re.finditer(r'<option\s+value="(\d+)"[^>]*>(.*?)</option>', texto, re.S)}
    ocupado = _json_despues_de(texto, r"const\s+occupied\s*=\s*")
    eventos = _json_despues_de(texto, r"\bevents\s*:\s*")
    horarios = _json_despues_de(texto, r"const\s+slots\s*=\s*") or []

    if not salas:
        raise PaginaInvalida("no encontré la lista de salas")
    if ocupado is None:
        raise PaginaInvalida("no encontré 'const occupied' (¿cambió la página?)")
    if eventos is None:
        raise PaginaInvalida("no encontré los eventos del calendario")
    if isinstance(ocupado, list):  # PHP json_encode([]) cuando no hay reservas
        ocupado = {}
    if not isinstance(ocupado, dict) or not isinstance(eventos, list):
        raise PaginaInvalida("formato inesperado de occupied/events")

    hoy = None
    m = re.search(r"const\s+today\s*=\s*['\"](\d{4}-\d{2}-\d{2})['\"]", texto)
    if m:
        hoy = date.fromisoformat(m.group(1))
    else:
        m = re.search(r"Hoy:\s*(\d{2})/(\d{2})/(\d{4})", texto)
        if m:
            hoy = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    return Pagina(hoy=hoy, salas=salas, horarios=list(horarios),
                  ocupado={str(k): v for k, v in ocupado.items()},
                  eventos=eventos, alertas=leer_alertas(texto))


def sala_libre(p: Pagina, sala: str, horario: str) -> bool:
    return not bool((p.ocupado.get(sala) or {}).get(horario))


def mi_reserva(p: Pagina, cfg: Config) -> dict | None:
    """Devuelve el evento del calendario que demuestra que el horario es tuyo (cualquier sala)."""
    for ev in p.eventos:
        props = ev.get("extendedProps") or {}
        if props.get("slot") != cfg.horario:
            continue
        if p.hoy and not str(ev.get("start", "")).startswith(p.hoy.isoformat()):
            continue
        if normalizar(ev.get("title", "")).startswith(cfg.clave_nombre):
            return ev
    return None


# ───────────────────────────── el bot ──────────────────────────────────

@dataclass
class Intento:
    estado: str  # confirmada | rechazada | no_confirmada | dry_run
    mensaje: str = ""
    evento: dict | None = None
    pagina: "Pagina | None" = None   # la lectura más reciente, para el siguiente de la fila


class Bot:
    def __init__(self, cfg: Config, fuente=None, clave=None, ticket: int | None = None, ref: str = "main"):
        self.cfg = cfg
        self.ticket = ticket          # número de ticket si esta es una corrida aislada
        self.ref = ref
        self.fuente = fuente          # solicitudes.GitHubIssues (o un falso en las pruebas)
        self.clave = clave            # llave privada para descifrar solicitudes
        self.personas: list[Persona] = []
        self.sala_duenio = cfg.salas[0] if cfg.salas else ""   # tu sala favorita
        self.hora_cambio_dia: datetime | None = None
        self.invalidas: set[int] = set()
        self.aviso_cupo: set[int] = set()
        self.sesion = requests.Session()
        self.sesion.headers.update({
            "User-Agent": f"Mozilla/5.0 (compatible; ReservaSalasUPB/{VERSION})",
            "Cache-Control": "no-cache",
        })
        self.resumen: list[str] = []

    # -- red --
    # Timeouts cortos a propósito: si el servidor "a veces tarda como media
    # hora", lo PEOR que puede hacer el bot es quedarse esos 30 min pegado a
    # una sola conexión sin poder reaccionar a nada más. Mejor cortar rápido
    # (25-30 s) y reintentar: así, si el servidor está lento, lo seguimos
    # consultando en vez de quedarnos congelados esperándolo.
    def obtener(self) -> Pagina:
        r = self.sesion.get(self.cfg.url, timeout=25)
        r.raise_for_status()
        return parsear(r.text)

    # -- tiempo --
    # Dos capas alrededor de la apertura del día siguiente:
    #   NÚCLEO (±15 min, p. ej. 19:45–20:15 BO): ritmo máximo (intervalo_rafaga),
    #     cubre sobrado la duda entre que abra a las 19:59 o a las 20:00.
    #   BANDA  (±60 min, p. ej. 19:00–21:00 BO): ritmo medio (intervalo_medio),
    #     por si el servidor anda lento/inestable y la apertura se corre.
    NUCLEO_ANTES = timedelta(minutes=15)
    NUCLEO_DESPUES = timedelta(minutes=15)
    BANDA_ANTES = timedelta(minutes=60)
    BANDA_DESPUES = timedelta(minutes=60)

    def apertura_de_hoy(self, ahora: datetime) -> datetime:
        h, m = map(int, self.cfg.apertura_bo.split(":"))
        return ahora.replace(hour=h, minute=m, second=0, microsecond=0)

    def fin_por_reloj(self, ahora: datetime) -> datetime | None:
        """Hora Bolivia a la que debe terminar esta ejecución (hoy), o None si no hay límite."""
        if not self.cfg.hasta_bo:
            return None
        h, m = map(int, self.cfg.hasta_bo.split(":"))
        return ahora.replace(hour=h, minute=m, second=0, microsecond=0)

    def proxima_apertura(self, ahora: datetime) -> datetime:
        h, m = map(int, self.cfg.apertura_bo.split(":"))
        hoy_apertura = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
        return (hoy_apertura if ahora <= hoy_apertura + self.BANDA_DESPUES
                else hoy_apertura + timedelta(days=1))

    def en_nucleo_apertura(self, ahora: datetime) -> bool:
        ap = self.proxima_apertura(ahora)
        return ap - self.NUCLEO_ANTES <= ahora <= ap + self.NUCLEO_DESPUES

    def en_banda_apertura(self, ahora: datetime) -> bool:
        ap = self.proxima_apertura(ahora)
        return ap - self.BANDA_ANTES <= ahora <= ap + self.BANDA_DESPUES

    def segundos_hasta_banda(self, ahora: datetime) -> float:
        return (self.proxima_apertura(ahora) - self.BANDA_ANTES - ahora).total_seconds()

    def horario_ya_paso(self, hoy: date | None, ahora: datetime, horario: str | None = None) -> bool:
        if hoy is None or hoy != ahora.date():
            return False  # si el servidor ya está en el día siguiente, el horario es futuro
        h, m = hora_fin(horario or self.cfg.horario)
        return ahora >= ahora.replace(hour=h, minute=m, second=0, microsecond=0) - timedelta(minutes=15)

    @staticmethod
    def backoff(errores_seguidos: int, intervalo: float, en_banda: bool) -> float:
        """Espera tras un error de red. Techo más bajo dentro de la banda
        (19:00-21:00 BO) para recuperarse rápido si el servidor tiene un
        bache justo cuando más importa; techo normal el resto del día para
        no insistirle de más a un servidor caído sin necesidad."""
        techo = 8.0 if en_banda else 60.0
        return min(techo, intervalo * 2 ** min(errores_seguidos, 5))

    # -- reserva --
    def intentar(self, p: Pagina, sala: str, per: Persona) -> Intento:
        cfg = self.cfg
        quien = "" if per.es_duenio else f"[{per.etiqueta}] "
        nombre_sala = p.salas.get(sala, f"sala {sala}")
        if cfg.dry_run:
            log(f"{quien}[DRY-RUN] {nombre_sala} {per.horario} está libre: aquí enviaría la reserva.")
            return Intento("dry_run", pagina=p)

        log(f"{quien}¡{nombre_sala} {per.horario} libre! Enviando reserva…")
        datos = {"room": sala, "first_name": per.nombre, "last_name": per.apellido,
                 "code": per.codigo, "schedule": per.horario, "purpose": per.proposito}
        alertas: list[tuple[str, str]] = []
        fallo_red = False
        try:
            r = self.sesion.post(cfg.url, data=datos, timeout=30, headers={"Referer": cfg.url})
            alertas = leer_alertas(r.text)
            log(f"{quien}Respuesta HTTP {r.status_code}. Mensajes del servidor: {alertas or 'ninguno'}")
        except requests.RequestException as e:
            fallo_red = True
            log(f"{quien}La conexión falló durante el envío ({e.__class__.__name__}). Verifico igual por si entró.")

        dijo_exito = any(t == "success" for t, _ in alertas)
        rechazo = next((msg for t, msg in alertas if t in ("danger", "warning")), "")

        # Verificación: la única fuente de verdad es el calendario del servidor.
        intentos = 8 if (dijo_exito or fallo_red) else 3
        ultima = p
        for k in range(intentos):
            if k:
                cfg.dormir(cfg.pausa_verificacion)
            try:
                q = self.obtener()
                ultima = q
            except (requests.RequestException, PaginaInvalida) as e:
                log(f"  verificación {k + 1}/{intentos}: no pude leer la página ({e})")
                continue
            ev = mi_reserva(q, per)
            if ev:
                log(f"  verificación {k + 1}/{intentos}: CONFIRMADA en el calendario → {ev.get('title')}")
                return Intento("confirmada", evento=ev, pagina=q)
            log(f"  verificación {k + 1}/{intentos}: todavía no aparece el nombre en {per.horario}")

        if dijo_exito:
            log(f"{quien}⚠️  El servidor mostró 'éxito' pero la reserva NO aparece en el calendario. "
                "NO se cuenta como reservada; sigo intentando.")
            return Intento("no_confirmada", "éxito sin confirmar", pagina=ultima)
        if rechazo:
            return Intento("rechazada", rechazo, pagina=ultima)
        return Intento("no_confirmada", "sin respuesta clara del servidor", pagina=ultima)

    # -- notificaciones / resumen --
    def notificar(self, texto: str, topic: str | None = None) -> None:
        topic = self.cfg.ntfy_topic if topic is None else topic
        if not topic:
            return
        try:
            requests.post(f"https://ntfy.sh/{topic}", data=texto.encode("utf-8"),
                          headers={"Title": "Reserva UPB"}, timeout=10)
        except requests.RequestException:
            pass

    def escribir_resumen(self, titulo: str) -> None:
        ruta = os.getenv("GITHUB_STEP_SUMMARY")
        if not ruta:
            return
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"## {titulo}\n\n" + "\n".join(f"- {l}" for l in self.resumen) + "\n")

    def terminar(self, codigo: int, titulo: str, anotacion: str = "notice") -> int:
        log(titulo)
        print(f"::{anotacion}::{titulo}", flush=True)
        self.escribir_resumen(titulo)
        return codigo

    # -- tickets de otros estudiantes (cada uno en su PROPIA corrida) --
    def auto_aprobacion_activa(self, ahora: datetime) -> bool:
        if not self.cfg.auto_aprobar:
            return False
        h, m = map(int, self.cfg.auto_aprobar_bo.split(":"))
        return ahora >= ahora.replace(hour=h, minute=m, second=0, microsecond=0)

    def ticket_listo(self, iss, p: Pagina, ahora: datetime) -> bool:
        """¿Toca lanzar ya la corrida aislada de este ticket?"""
        if not iss.abierto or "rechazada" in iss.etiquetas or "en-curso" in iss.etiquetas:
            return False
        if "aprobada" not in iss.etiquetas and not self.auto_aprobacion_activa(ahora):
            return False  # pendiente: espera tu aprobación o la auto-aprobación
        if iss.fecha is None or p.hoy is None:
            return True   # la corrida valida la fecha real (cifrada) y se cierra sola si no corresponde
        if iss.fecha == p.hoy:
            return True   # mismo día: buscar cancelaciones ahora
        # día siguiente: lanzar desde las 15:30 BO para que la corrida cubra la apertura de las 20:00
        return iss.fecha == p.hoy + timedelta(days=1) and ahora.hour * 60 + ahora.minute >= 15 * 60 + 30

    def despachar_tickets(self, p: Pagina, ahora: datetime) -> None:
        """Solo enruta números de ticket: NO descifra ni guarda datos de nadie."""
        if not self.fuente or self.cfg.dry_run:
            return
        try:
            tickets = sorted(self.fuente.listar(), key=lambda i: i.numero)
        except Exception as e:
            log(f"No pude leer los tickets ({e.__class__.__name__}); lo reintento luego.")
            return
        en_curso = sum(1 for t in tickets if "en-curso" in t.etiquetas)
        cupo = self.cfg.max_personas - 1
        for t in tickets:
            if not self.ticket_listo(t, p, ahora):
                continue
            if en_curso >= cupo:
                if t.numero not in self.aviso_cupo:
                    self.aviso_cupo.add(t.numero)
                    log(f"Ticket #{t.numero}: cupo lleno ({self.cfg.max_personas} personas por noche); queda en espera.")
                continue
            if self.fuente.despachar(t.numero, self.ref):
                self.fuente.etiquetar(t.numero, ["en-curso"])
                en_curso += 1
                self.resumen.append(f"Ticket #{t.numero}: corrida aislada lanzada")
                log(f"Ticket #{t.numero}: lancé su corrida aislada.")

    def cerrar_ticket(self, per: Persona, etiqueta: str, texto: str) -> None:
        """Comenta el resultado (sin datos personales), BORRA los datos cifrados y cierra."""
        if self.fuente and per.issue and not self.cfg.dry_run:
            self.fuente.comentar(per.issue, texto)
            self.fuente.etiquetar(per.issue, [etiqueta])
            self.fuente.quitar_etiqueta(per.issue, "en-curso")
            self.fuente.borrar_datos(per.issue)
            self.fuente.cerrar(per.issue)
        per.cerrada = True

    # compatibilidad con el nombre anterior
    cerrar_solicitud = cerrar_ticket

    def descartar_ticket(self, numero: int, motivo: str) -> None:
        log(f"Ticket #{numero} descartado: {motivo}")
        if self.fuente and not self.cfg.dry_run:
            self.fuente.comentar(numero, f"❌ Solicitud descartada: {motivo}.")
            self.fuente.etiquetar(numero, ["invalida"])
            self.fuente.quitar_etiqueta(numero, "en-curso")
            self.fuente.borrar_datos(numero)
            self.fuente.cerrar(numero)

    def preparar_ticket(self, p: Pagina) -> Persona | None:
        """Corrida aislada: lee SOLO este ticket, lo descifra en memoria y arma a la persona."""
        from solicitudes import SolicitudInvalida, descifrar, validar
        n = self.ticket
        try:
            iss = self.fuente.obtener(n)
        except Exception as e:
            log(f"No pude leer el ticket #{n} ({e.__class__.__name__}).")
            return None
        if iss is None or not iss.abierto or "rechazada" in iss.etiquetas or MARCADOR_TICKET not in iss.cuerpo:
            log(f"Ticket #{n}: ya no está activo (eliminado, cerrado o rechazado). Termino sin hacer nada.")
            return None
        try:
            datos = validar(descifrar(iss.cuerpo, self.clave), p.salas, p.horarios)
        except SolicitudInvalida as e:
            self.descartar_ticket(n, str(e))
            return None
        if datos["codigo"] == self.cfg.codigo:
            self.descartar_ticket(n, "usa el mismo código que la reserva principal")
            return None
        for v in (f"{datos['nombre']} {datos['apellido']}", datos["nombre"], datos["apellido"],
                  datos["codigo"], datos["ntfy"]):
            if v and len(v) >= 4:
                print(f"::add-mask::{v}", flush=True)  # GitHub oculta estos datos en los logs públicos
        log(f"Ticket #{n}: {datos['horario']} el {datos['fecha']}, salas {datos['salas']}")
        return Persona(nombre=datos["nombre"], apellido=datos["apellido"], codigo=datos["codigo"],
                       salas=datos["salas"], horario=datos["horario"], proposito=datos["proposito"],
                       etiqueta=f"ticket #{n}", fecha=datos["fecha"], ntfy=datos["ntfy"], issue=n)

    def registrar_hecha(self, per: Persona, ev: dict, p: Pagina) -> None:
        per.hecha_en = p.hoy
        sala = (ev.get("extendedProps") or {}).get("room", "")
        if per.es_duenio:
            linea = f"{p.hoy}: {ev.get('title')} {per.horario} ✅ confirmada en el calendario"
            if linea not in self.resumen:
                self.resumen.append(linea)
            log(("RESERVA CONFIRMADA: " if per.reservada_aqui else "Ya tenías la reserva: ") + linea)
            if per.reservada_aqui:
                self.notificar(f"✅ Reservado y verificado: {ev.get('title')} {per.horario} ({p.hoy})")
            return
        texto = f"✅ Reservado y verificado: {sala} · {per.horario} · {p.hoy}"
        self.resumen.append(f"{per.etiqueta}: {sala} {per.horario} ✅")
        log(f"{per.etiqueta}: {'RESERVA CONFIRMADA' if per.reservada_aqui else 'ya tenía la reserva'} → {sala}")
        self.notificar(texto, topic=per.ntfy)
        self.notificar(f"✅ {per.etiqueta}: {sala} {per.horario} ({p.hoy})")
        self.cerrar_solicitud(per, "reservada", texto)

    def atender(self, per: Persona, p: Pagina, ahora: datetime) -> tuple[str, Pagina]:
        """Devuelve (estado, página más reciente). estado: hecha | espera | vigila | dry | abortar | fuera."""
        cfg = self.cfg
        if per.cerrada:
            return "fuera", p
        if per.fecha and p.hoy and p.hoy > per.fecha:
            self.cerrar_solicitud(per, "sin-sala", f"❌ No se consiguió sala para {per.fecha}.")
            self.notificar(f"❌ No se consiguió sala para {per.fecha}.", topic=per.ntfy)
            return "fuera", p
        if per.fecha and p.hoy != per.fecha:
            return "espera", p
        ev = mi_reserva(p, per)
        if ev:
            if per.hecha_en != p.hoy:
                self.registrar_hecha(per, ev, p)
            return "hecha", p
        if self.horario_ya_paso(p.hoy, ahora, per.horario):
            return "espera", p
        libres = [s for s in per.salas if sala_libre(p, s, per.horario)]
        if not per.es_duenio and self.sala_duenio and self.hora_cambio_dia and \
                (cfg.reloj() - self.hora_cambio_dia).total_seconds() < PRIORIDAD_DUENIO_SEG:
            libres = [s for s in libres if s != self.sala_duenio]  # tu sala favorita es primero tuya
        if not libres:
            return "vigila", p
        intento = self.intentar(p, libres[0], per)
        q = intento.pagina or p
        if intento.estado == "dry_run":
            per.hecha_en = p.hoy
            self.resumen.append(f"{p.hoy}: {per.etiqueta}: {p.salas[libres[0]]} {per.horario} libre "
                                "(dry-run, no se envió)")
            return "dry", q
        if intento.estado == "confirmada":
            per.reservada_aqui = True
            if self.hora_cambio_dia:
                reaccion = (cfg.reloj() - self.hora_cambio_dia).total_seconds()
                self.resumen.append(f"⏱️ {per.etiqueta}: confirmada {reaccion:.1f} s después de detectar el cambio de día")
            self.registrar_hecha(per, intento.evento, q)
            return "hecha", q
        if intento.estado == "rechazada":
            if intento.mensaje == per.ultimo_rechazo:
                per.rechazos_iguales += 1
            else:
                per.ultimo_rechazo, per.rechazos_iguales = intento.mensaje, 1
            log(f"{per.etiqueta}: rechazada por el servidor ({per.rechazos_iguales}/{cfg.max_rechazos}): {intento.mensaje}")
            if per.rechazos_iguales >= cfg.max_rechazos:
                if per.es_duenio:
                    self.resumen.append(f"Rechazo repetido: {intento.mensaje}")
                    return "abortar", q
                self.cerrar_solicitud(per, "rechazada-por-el-sitio",
                                      f"❌ El sistema de reservas rechazó la solicitud varias veces: {intento.mensaje}")
                return "fuera", q
        return "vigila", q

    # -- bucle principal --
    def ejecutar(self) -> int:
        cfg = self.cfg
        ahora0 = cfg.reloj()
        segundos = cfg.max_segundos
        hasta = self.fin_por_reloj(ahora0)
        if hasta is not None:
            segundos = min(segundos, max(0.0, (hasta - ahora0).total_seconds()))
        fin = time.monotonic() + segundos
        log(f"Bot v{VERSION} | {cfg.nombre} {cfg.apellido} ({cfg.codigo_oculto}) | horario {cfg.horario} | "
            f"salas {cfg.salas} | {'DRY-RUN' if cfg.dry_run else 'real'} | arranqué {ahora0:%H:%M} BO, "
            f"termino {(ahora0 + timedelta(seconds=segundos)):%H:%M} BO | "
            + (f"corrida AISLADA del ticket #{self.ticket}" if self.ticket else
               f"tickets {'activos' if self.fuente and self.clave else 'desactivados'}"))
        duenio = Persona(nombre=cfg.nombre, apellido=cfg.apellido, codigo=cfg.codigo, salas=list(cfg.salas),
                         horario=cfg.horario, proposito=cfg.proposito, etiqueta="tú", es_duenio=True)
        # En una corrida de ticket la única persona es la del ticket (se arma tras leer la página).
        self.personas = [] if self.ticket else [duenio]
        tarde = (not cfg.dry_run) and bool(cfg.hasta_bo) and not self.ticket \
            and ahora0 > self.apertura_de_hoy(ahora0) + timedelta(minutes=2)
        aviso_tarde_hecho = False
        latido_hecho = False
        self.hora_cambio_dia = None
        proxima_recarga = 0.0
        auto_antes = self.auto_aprobacion_activa(ahora0)

        lecturas_ok = 0
        errores_seguidos = 0
        validado = False
        ultimo_hoy: date | None = None
        consultas = 0

        while True:
            if consultas and time.monotonic() >= fin:
                break
            consultas += 1
            ahora = cfg.reloj()
            try:
                p = self.obtener()
                lecturas_ok += 1
                errores_seguidos = 0
            except (requests.RequestException, PaginaInvalida) as e:
                errores_seguidos += 1
                espera = self.backoff(errores_seguidos, cfg.intervalo, self.en_banda_apertura(ahora))
                log(f"No pude leer la página ({e}). Reintento en {espera:.0f}s.")
                cfg.dormir(espera)
                continue

            if not validado and self.ticket:
                persona_ticket = self.preparar_ticket(p)
                if persona_ticket is None:
                    return self.terminar(EXIT_OK, f"Ticket #{self.ticket}: nada que hacer.")
                self.personas = [persona_ticket]
                duenio = persona_ticket  # la "principal" de esta corrida
                self.notificar(f"🟢 Tu solicitud está activa: el bot vigila {persona_ticket.horario} "
                               f"para el {persona_ticket.fecha}.", topic=persona_ticket.ntfy)
                validado = True
            if not validado:
                desconocidas = [s for s in cfg.salas if s not in p.salas]
                if desconocidas:
                    return self.terminar(EXIT_CONFIG, f"Salas inexistentes: {desconocidas}. Disponibles: {p.salas}", "error")
                if p.horarios and cfg.horario not in p.horarios:
                    return self.terminar(EXIT_CONFIG, f"Horario {cfg.horario} no existe. Disponibles: {p.horarios}", "error")
                log("Salas objetivo: " + ", ".join(f"{s}={p.salas[s]}" for s in cfg.salas))
                validado = True

            if ultimo_hoy is not None and p.hoy != ultimo_hoy:
                self.hora_cambio_dia = cfg.reloj()
                linea = f"📅 El servidor cambió a {p.hoy} a las {self.hora_cambio_dia:%H:%M:%S} BO"
                self.resumen.append(linea)
                log(linea)
            if p.hoy != ultimo_hoy:
                log(f"Fecha del servidor: {p.hoy}")
                ultimo_hoy = p.hoy

            # Tickets: tu corrida solo LANZA la corrida aislada de cada ticket listo (cada 5 min y
            # al cruzar la hora de auto-aprobación). Nunca dentro del núcleo de la apertura.
            auto_ahora = self.auto_aprobacion_activa(ahora)
            if self.fuente and not self.ticket and not self.en_nucleo_apertura(ahora) and \
                    (time.monotonic() >= proxima_recarga or auto_ahora != auto_antes):
                self.despachar_tickets(p, ahora)
                proxima_recarga = time.monotonic() + 300
                auto_antes = auto_ahora

            ev = mi_reserva(p, duenio)

            # Arranque tardío: GitHub puede retrasar mucho los cron.
            if tarde and not ev and not aviso_tarde_hecho:
                aviso_tarde_hecho = True
                msg = (f"⚠️ El bot arrancó tarde ({ahora0:%H:%M} BO), después de la apertura de las "
                       f"{cfg.apertura_bo}. Reserva a mano si puedes; igual sigo intentando.")
                self.resumen.append(msg)
                print(f"::warning::{msg}", flush=True)
                self.notificar(msg)
                if time.monotonic() >= fin:  # ya pasó también la hora de fin
                    return self.terminar(EXIT_TARDE, msg, "error")
            if ev and time.monotonic() >= fin:
                return self.terminar(EXIT_OK, "Ya tenías la reserva ✅ (no hice nada)")

            # Latido: confirma al celular que el bot está vivo antes de la apertura.
            if not latido_hecho and not ev and self.en_banda_apertura(ahora) and not cfg.dry_run:
                latido_hecho = True
                if not self.ticket:
                    self.notificar(f"🟢 Bot vigilando: salas {', '.join(p.salas.get(s, s) for s in cfg.salas)} "
                                   f"· {cfg.horario}")

            # Atender a todos con la MISMA lectura (no se multiplica la carga al sitio).
            estados = []
            for per in [x for x in self.personas if not x.cerrada]:
                estado, p = self.atender(per, p, ahora)
                estados.append(estado)
                if estado == "abortar":
                    return self.terminar(EXIT_RECHAZOS, "El servidor rechazó la reserva varias veces "
                                         "con el mismo mensaje. Revísalo a mano.", "error")
            if "dry" in estados:
                return self.terminar(EXIT_OK, "Dry-run terminado: el bot habría reservado.")
            if "vigila" in estados and (consultas == 1 or consultas % 50 == 0):
                log(f"Horarios ocupados en las salas objetivo. Vigilando… (consulta {consultas})")
            if not self.personas or all(x.cerrada for x in self.personas):
                return self.terminar(EXIT_OK, f"Ticket #{self.ticket} terminado." if self.ticket
                                     else "Nada más que hacer.")
            if duenio.hecha_en is None and estados and estados[0] == "espera" and consultas == 1 \
                    and self.horario_ya_paso(p.hoy, ahora, duenio.horario):
                log(f"El horario {cfg.horario} de hoy ya pasó; espero la apertura del día siguiente.")
            sin_nada_que_hacer = "vigila" not in estados

            # ¿Cuánto esperar? Tres niveles: núcleo (rafaga) > banda (medio) > normal.
            if sin_nada_que_hacer:
                hasta_banda = self.segundos_hasta_banda(ahora)
                if not self.en_banda_apertura(ahora) and time.monotonic() + hasta_banda > fin:
                    if duenio.hecha_en == p.hoy:
                        return self.terminar(EXIT_OK, "Reserva confirmada ✅" if duenio.reservada_aqui
                                             else "Ya tenías la reserva ✅ (no hice nada)")
                    return self.terminar(EXIT_OK, "Horario de hoy ya pasó y la próxima apertura cae fuera de esta ejecución.")
                if self.en_nucleo_apertura(ahora):
                    espera = cfg.intervalo_rafaga
                elif self.en_banda_apertura(ahora):
                    espera = cfg.intervalo_medio
                else:
                    lejos = 300.0 if hasta_banda > 15 * 60 else cfg.intervalo_espera
                    espera = min(lejos, max(1.0, hasta_banda))
                    if self.fuente:  # que la recarga de solicitudes no espere de más
                        espera = min(espera, max(1.0, proxima_recarga - time.monotonic()))
            elif self.en_nucleo_apertura(ahora):
                espera = cfg.intervalo_rafaga
            elif self.en_banda_apertura(ahora):
                espera = cfg.intervalo_medio
            else:
                espera = cfg.intervalo * random.uniform(1.0, 1.3)
            cfg.dormir(max(0.0, min(espera, fin - time.monotonic())))

        if lecturas_ok == 0:
            return self.terminar(EXIT_SITIO, "No pude leer la página en toda la ejecución.", "error")
        # Cierre de la noche para las solicitudes que no lograron sala.
        if latido_hecho or aviso_tarde_hecho or self.ticket:
            for per in self.personas:
                if not per.es_duenio and not per.cerrada and per.hecha_en is None and per.fecha == ultimo_hoy \
                        and (latido_hecho or self.horario_ya_paso(ultimo_hoy, cfg.reloj(), per.horario)
                             or self.fin_por_reloj(ahora0) is not None):
                    self.resumen.append(f"{per.etiqueta}: sin sala ❌")
                    self.notificar(f"❌ No se consiguió sala para {per.fecha}.", topic=per.ntfy)
                    self.cerrar_solicitud(per, "sin-sala", f"❌ No se consiguió sala para {per.fecha}.")
        if self.ticket:
            return self.terminar(EXIT_OK, f"Ticket #{self.ticket}: " + (
                "reserva confirmada ✅" if duenio.reservada_aqui else "terminado sin sala."))
        if duenio.reservada_aqui:
            return self.terminar(EXIT_OK, "Reserva confirmada ✅")
        if duenio.hecha_en is not None and duenio.hecha_en == ultimo_hoy:
            return self.terminar(EXIT_OK, "Ya tenías la reserva ✅ (no hice nada)")
        self.resumen.append(f"{ultimo_hoy}: {cfg.horario} no se liberó durante esta ejecución")
        if latido_hecho or aviso_tarde_hecho:
            self.notificar(f"❌ Terminé sin conseguir sala para {ultimo_hoy} {cfg.horario}. Revisa a mano.")
        return self.terminar(EXIT_OK, "Tiempo agotado: no se liberó la sala (no se reservó nada).", "warning")


def fuente_desde_entorno():  # noqa: C901
    """Activa las solicitudes de terceros si están todos los datos; si no, el bot sigue solo contigo."""
    if os.getenv("UPB_SOLICITUDES", "1").strip().lower() in ("0", "false", "no"):
        return None, None
    token, repo, priv = (os.getenv(v, "").strip() for v in ("UPB_GH_TOKEN", "UPB_REPO", "UPB_CLAVE_PRIVADA"))
    if not (token and repo and priv):
        log("Solicitudes de otros: desactivadas (falta UPB_CLAVE_PRIVADA; créala desde la Guía del panel).")
        return None, None
    try:
        import solicitudes
        return solicitudes.GitHubIssues(repo, token, log=log), solicitudes.cargar_clave_privada(priv)
    except Exception as e:
        print(f"::warning::No pude activar las solicitudes ({e.__class__.__name__}). Sigo solo con tu reserva.")
        return None, None


def main() -> int:
    try:
        cfg = Config.desde_entorno()
    except ValueError as e:
        print(f"::error::{e}", flush=True)
        return EXIT_CONFIG
    fuente, clave = fuente_desde_entorno()
    ticket = os.getenv("UPB_TICKET", "").strip()
    if ticket:
        if not ticket.isdigit():
            print("::error::UPB_TICKET debe ser un número de ticket", flush=True)
            return EXIT_CONFIG
        if not (fuente and clave):
            print("::error::Corrida de ticket sin UPB_CLAVE_PRIVADA: no puedo leer la solicitud.", flush=True)
            return EXIT_CONFIG
        for k, v in RITMO_TICKET.items():  # constantes de código, no configurables
            setattr(cfg, k, v)
    bot = Bot(cfg, fuente=fuente, clave=clave, ticket=int(ticket) if ticket else None,
              ref=os.getenv("GITHUB_REF_NAME", "main") or "main")
    bot.sala_duenio = (os.getenv("UPB_SALA_DUENIO", "") or (cfg.salas[0] if cfg.salas else "")).strip()
    return bot.ejecutar()


if __name__ == "__main__":
    sys.exit(main())
