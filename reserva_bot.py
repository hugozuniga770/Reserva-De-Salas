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
  UPB_MAX_MINUTOS  duración máxima de la ejecución (def. 112)
  UPB_APERTURA_BO  hora Bolivia en que el servidor abre el día siguiente (def. "20:00")
  UPB_DRY_RUN      "1" = no envía nada, sólo dice qué haría
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

EXIT_OK, EXIT_CONFIG, EXIT_RECHAZOS, EXIT_SITIO = 0, 1, 2, 3


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
    max_segundos: float = 112 * 60
    intervalo: float = 2.0            # buscando una sala que se libere
    intervalo_medio: float = 1.0      # banda ancha alrededor de la apertura
    intervalo_rafaga: float = 0.25    # núcleo de la apertura del día siguiente
    intervalo_espera: float = 30.0    # cuando ya no hay nada que hacer hasta la banda
    pausa_verificacion: float = 2.0
    apertura_bo: str = "20:00"
    dry_run: bool = False
    max_rechazos: int = 5
    ntfy_topic: str = ""
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
        return cls(
            nombre=os.environ["UPB_NOMBRE"].strip(),
            apellido=os.environ["UPB_APELLIDO"].strip(),
            codigo=os.environ["UPB_CODIGO"].strip(),
            salas=salas,
            horario=normalizar_horario(os.getenv("UPB_HORARIO", "12:15-14:15")),
            proposito=os.getenv("UPB_PROPOSITO", "Estudio académico").strip() or "Estudio académico",
            url=os.getenv("UPB_URL", URL_DEFECTO).strip(),
            max_segundos=float(os.getenv("UPB_MAX_MINUTOS", "112")) * 60,
            apertura_bo=apertura,
            dry_run=os.getenv("UPB_DRY_RUN", "0").strip().lower() in ("1", "true", "si", "sí", "yes"),
            ntfy_topic=os.getenv("NTFY_TOPIC", "").strip(),
        )


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


class Bot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
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

    def horario_ya_paso(self, hoy: date | None, ahora: datetime) -> bool:
        if hoy is None or hoy != ahora.date():
            return False  # si el servidor ya está en el día siguiente, el horario es futuro
        h, m = hora_fin(self.cfg.horario)
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
    def intentar(self, p: Pagina, sala: str) -> Intento:
        cfg = self.cfg
        nombre_sala = p.salas.get(sala, f"sala {sala}")
        if cfg.dry_run:
            log(f"[DRY-RUN] {nombre_sala} {cfg.horario} está libre: aquí enviaría la reserva.")
            return Intento("dry_run")

        log(f"¡{nombre_sala} {cfg.horario} libre! Enviando reserva…")
        datos = {"room": sala, "first_name": cfg.nombre, "last_name": cfg.apellido,
                 "code": cfg.codigo, "schedule": cfg.horario, "purpose": cfg.proposito}
        alertas: list[tuple[str, str]] = []
        fallo_red = False
        try:
            r = self.sesion.post(cfg.url, data=datos, timeout=30, headers={"Referer": cfg.url})
            alertas = leer_alertas(r.text)
            log(f"Respuesta HTTP {r.status_code}. Mensajes del servidor: {alertas or 'ninguno'}")
        except requests.RequestException as e:
            fallo_red = True
            log(f"La conexión falló durante el envío ({e.__class__.__name__}). Verifico igual por si entró.")

        dijo_exito = any(t == "success" for t, _ in alertas)
        rechazo = next((msg for t, msg in alertas if t in ("danger", "warning")), "")

        # Verificación: la única fuente de verdad es el calendario del servidor.
        # Más intentos que antes por si el servidor tarda en guardar cuando
        # anda con tráfico alto (hora pico de reservas).
        intentos = 8 if (dijo_exito or fallo_red) else 3
        for k in range(intentos):
            if k:
                cfg.dormir(cfg.pausa_verificacion)
            try:
                q = self.obtener()
            except (requests.RequestException, PaginaInvalida) as e:
                log(f"  verificación {k + 1}/{intentos}: no pude leer la página ({e})")
                continue
            ev = mi_reserva(q, cfg)
            if ev:
                log(f"  verificación {k + 1}/{intentos}: CONFIRMADA en el calendario → {ev.get('title')}")
                return Intento("confirmada", evento=ev)
            log(f"  verificación {k + 1}/{intentos}: todavía no aparece tu nombre en {cfg.horario}")

        if dijo_exito:
            log("⚠️  El servidor mostró 'éxito' pero la reserva NO aparece en el calendario. "
                "NO se cuenta como reservada; sigo intentando.")
            return Intento("no_confirmada", "éxito sin confirmar")
        if rechazo:
            return Intento("rechazada", rechazo)
        return Intento("no_confirmada", "sin respuesta clara del servidor")

    # -- notificaciones / resumen --
    def notificar(self, texto: str) -> None:
        if not self.cfg.ntfy_topic:
            return
        try:
            requests.post(f"https://ntfy.sh/{self.cfg.ntfy_topic}", data=texto.encode("utf-8"),
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

    # -- bucle principal --
    def ejecutar(self) -> int:
        cfg = self.cfg
        fin = time.monotonic() + cfg.max_segundos
        log(f"Bot v{VERSION} | {cfg.nombre} {cfg.apellido} ({cfg.codigo_oculto}) | horario {cfg.horario} | "
            f"salas {cfg.salas} | {'DRY-RUN' if cfg.dry_run else 'real'} | máx {cfg.max_segundos / 60:.0f} min")

        lecturas_ok = 0
        errores_seguidos = 0
        validado = False
        reservada_aqui = False
        ultimo_hoy: date | None = None
        ultimo_rechazo, rechazos_iguales = "", 0
        consultas = 0

        while time.monotonic() < fin:
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

            if not validado:
                desconocidas = [s for s in cfg.salas if s not in p.salas]
                if desconocidas:
                    return self.terminar(EXIT_CONFIG, f"Salas inexistentes: {desconocidas}. Disponibles: {p.salas}", "error")
                if p.horarios and cfg.horario not in p.horarios:
                    return self.terminar(EXIT_CONFIG, f"Horario {cfg.horario} no existe. Disponibles: {p.horarios}", "error")
                log("Salas objetivo: " + ", ".join(f"{s}={p.salas[s]}" for s in cfg.salas))
                validado = True

            if p.hoy != ultimo_hoy:
                log(f"Fecha del servidor: {p.hoy}")
                ultimo_hoy = p.hoy
                ultimo_rechazo, rechazos_iguales = "", 0

            ev = mi_reserva(p, cfg)
            sin_nada_que_hacer = False

            if ev:
                sin_nada_que_hacer = True
                linea = f"{p.hoy}: {ev.get('title')} {cfg.horario} ✅ confirmada en el calendario"
                if linea not in self.resumen:
                    self.resumen.append(linea)
                    log(("RESERVA CONFIRMADA: " if reservada_aqui else "Ya tenías la reserva: ") + linea)
            elif self.horario_ya_paso(p.hoy, ahora):
                sin_nada_que_hacer = True
                if consultas == 1:
                    log(f"El horario {cfg.horario} de hoy ya pasó; espero la apertura del día siguiente.")
            else:
                libres = [s for s in cfg.salas if sala_libre(p, s, cfg.horario)]
                if libres:
                    intento = self.intentar(p, libres[0])
                    if intento.estado == "dry_run":
                        self.resumen.append(f"{p.hoy}: {p.salas[libres[0]]} {cfg.horario} libre (dry-run, no se envió)")
                        return self.terminar(EXIT_OK, "Dry-run terminado: el bot habría reservado.")
                    if intento.estado == "confirmada":
                        reservada_aqui = True
                        self.notificar(f"✅ Reservado y verificado: {intento.evento.get('title')} {cfg.horario} ({p.hoy})")
                        continue  # la siguiente vuelta lo registra y decide si termina
                    if intento.estado == "rechazada":
                        if intento.mensaje == ultimo_rechazo:
                            rechazos_iguales += 1
                        else:
                            ultimo_rechazo, rechazos_iguales = intento.mensaje, 1
                        log(f"Rechazada por el servidor ({rechazos_iguales}/{cfg.max_rechazos}): {intento.mensaje}")
                        if rechazos_iguales >= cfg.max_rechazos:
                            self.resumen.append(f"Rechazo repetido: {intento.mensaje}")
                            return self.terminar(EXIT_RECHAZOS, "El servidor rechazó la reserva varias veces "
                                                 "con el mismo mensaje. Revísalo a mano.", "error")
                elif consultas == 1 or consultas % 50 == 0:
                    log(f"{cfg.horario} ocupado en todas las salas objetivo. Vigilando… (consulta {consultas})")

            # ¿Cuánto esperar? Tres niveles: núcleo (rafaga) > banda (medio) > normal.
            if sin_nada_que_hacer:
                hasta_banda = self.segundos_hasta_banda(ahora)
                if not self.en_banda_apertura(ahora) and time.monotonic() + hasta_banda > fin:
                    if ev:
                        return self.terminar(EXIT_OK, "Reserva confirmada ✅" if reservada_aqui
                                             else "Ya tenías la reserva ✅ (no hice nada)")
                    return self.terminar(EXIT_OK, "Horario de hoy ya pasó y la próxima apertura cae fuera de esta ejecución.")
                if self.en_nucleo_apertura(ahora):
                    espera = cfg.intervalo_rafaga
                elif self.en_banda_apertura(ahora):
                    espera = cfg.intervalo_medio
                else:
                    espera = min(cfg.intervalo_espera, max(1.0, hasta_banda))
            elif self.en_nucleo_apertura(ahora):
                espera = cfg.intervalo_rafaga
            elif self.en_banda_apertura(ahora):
                espera = cfg.intervalo_medio
            else:
                espera = cfg.intervalo * random.uniform(1.0, 1.3)
            cfg.dormir(max(0.0, min(espera, fin - time.monotonic())))

        if lecturas_ok == 0:
            return self.terminar(EXIT_SITIO, "No pude leer la página en toda la ejecución.", "error")
        if reservada_aqui:
            return self.terminar(EXIT_OK, "Reserva confirmada ✅")
        self.resumen.append(f"{ultimo_hoy}: {cfg.horario} no se liberó durante esta ejecución")
        return self.terminar(EXIT_OK, "Tiempo agotado: no se liberó la sala (no se reservó nada).", "warning")


def main() -> int:
    try:
        cfg = Config.desde_entorno()
    except ValueError as e:
        print(f"::error::{e}", flush=True)
        return EXIT_CONFIG
    return Bot(cfg).ejecutar()


if __name__ == "__main__":
    sys.exit(main())
