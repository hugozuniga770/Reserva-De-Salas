"""
Solicitudes (tickets) de reserva de otros estudiantes.

Principios:
  * NO existe una lista de usuarios. Cada solicitud es un ticket de UN SOLO USO.
  * Cada ticket se atiende en SU PROPIA corrida de GitHub Actions (aislada):
    esa corrida solo conoce los datos de esa persona, los descifra en memoria,
    reserva, BORRA los datos del ticket y lo cierra.
  * Si un ticket se elimina o se rechaza, su corrida no encuentra nada y termina;
    las demás corridas no se enteran ni se afectan.

Cada solicitud es un *issue* del repo cuyo cuerpo trae los datos CIFRADOS:
  - La página pública (docs/index.html#pedir) cifra en el navegador con la llave
    pública (docs/clave_publica.txt): AES-256-GCM para los datos y RSA-OAEP-SHA256
    para la llave AES.
  - Solo el bot (secret UPB_CLAVE_PRIVADA) y tu panel (llave guardada en tu
    teléfono) pueden leerla. En GitHub, que es público, solo se ve texto cifrado.

Formato del cuerpo:
    <!-- reserva-upb:v1 -->
    ...
    upbv1.<llave_envuelta_b64>.<iv_b64>.<datos_b64>
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date

import requests

MARCADOR = "<!-- reserva-upb:v1 -->"
PATRON = re.compile(r"upbv1\.([A-Za-z0-9+/=]+)\.([A-Za-z0-9+/=]+)\.([A-Za-z0-9+/=]+)")


class SolicitudInvalida(Exception):
    """El mensaje se publica en el issue: nunca incluir datos personales."""


# ───────────────────────────── cifrado ─────────────────────────────

def _b64d(s: str) -> bytes:
    return base64.b64decode(s + "=" * (-len(s) % 4))


def cargar_clave_privada(texto: str):
    from cryptography.hazmat.primitives import serialization
    limpio = re.sub(r"-----[^-]+-----|\s", "", texto or "")
    if not limpio:
        raise ValueError("UPB_CLAVE_PRIVADA está vacía")
    return serialization.load_der_private_key(_b64d(limpio), password=None)


def cifrar(datos: dict, clave_publica_b64: str) -> str:
    """Igual que docs/cifrado.js (se usa en las pruebas y para agregar a mano)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    pub = serialization.load_der_public_key(_b64d(re.sub(r"\s", "", clave_publica_b64)))
    k, iv = AESGCM.generate_key(256), os.urandom(12)
    c = AESGCM(k).encrypt(iv, json.dumps(datos, ensure_ascii=False).encode(), None)
    w = pub.encrypt(k, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    b = lambda x: base64.b64encode(x).decode()
    return f"upbv1.{b(w)}.{b(iv)}.{b(c)}"


def descifrar(cuerpo: str, clave) -> dict:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    m = PATRON.search(cuerpo or "")
    if not m:
        raise SolicitudInvalida("no encontré el bloque cifrado")
    try:
        k = clave.decrypt(_b64d(m.group(1)),
                          padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        datos = json.loads(AESGCM(k).decrypt(_b64d(m.group(2)), _b64d(m.group(3)), None))
    except Exception as e:
        raise SolicitudInvalida("no se pudo descifrar (¿se generó con otra llave?)") from e
    if not isinstance(datos, dict):
        raise SolicitudInvalida("contenido con formato inesperado")
    return datos


# ───────────────────────────── validación ─────────────────────────────

_NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]{2,60}$")


def _normal(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def validar(datos: dict, salas_pagina: dict[str, str], horarios_pagina: list[str]) -> dict:
    """Devuelve los campos limpios o lanza SolicitudInvalida (mensaje sin datos personales)."""
    nombre = str(datos.get("nombre", "")).strip()
    apellido = str(datos.get("apellido", "")).strip()
    codigo = str(datos.get("codigo", "")).strip()
    if not _NOMBRE.match(nombre) or not _NOMBRE.match(apellido):
        raise SolicitudInvalida("nombre o apellido con formato inválido")
    if not re.fullmatch(r"\d{3,10}", codigo):
        raise SolicitudInvalida("el código de estudiante debe tener solo números")

    horas = re.findall(r"(\d{1,2}):(\d{2})", str(datos.get("horario", "")))
    if len(horas) != 2:
        raise SolicitudInvalida("horario inválido")
    horario = "-".join(f"{int(h)}:{m}" for h, m in horas)
    if horarios_pagina and horario not in horarios_pagina:
        raise SolicitudInvalida(f"el horario {horario} no existe en el sistema")

    salas: list[str] = []
    for s in datos.get("salas") or []:
        s = str(s).strip()
        if s in salas_pagina and "estudio" in _normal(salas_pagina[s]) and s not in salas:
            salas.append(s)
    if not salas:
        raise SolicitudInvalida("no eligió ninguna sala de estudio válida")

    try:
        fecha = date.fromisoformat(str(datos.get("fecha", "")))
    except ValueError:
        raise SolicitudInvalida("fecha de uso inválida") from None

    ntfy = str(datos.get("ntfy", "") or "").strip()
    if ntfy and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ntfy):
        ntfy = ""
    proposito = str(datos.get("proposito", "") or "").strip()[:120] or "Estudio académico"
    return {"nombre": nombre, "apellido": apellido, "codigo": codigo, "horario": horario,
            "salas": salas[:6], "fecha": fecha, "ntfy": ntfy, "proposito": proposito}


# ───────────────────────────── GitHub ─────────────────────────────

@dataclass
class Issue:
    numero: int
    cuerpo: str
    etiquetas: set[str] = field(default_factory=set)
    titulo: str = ""
    abierto: bool = True
    autor: str = ""          # login de GitHub de quien abrió el ticket (no es un dato personal del formulario)

    @property
    def horario(self) -> str:
        m = re.search(r"\b(\d{1,2}:\d{2}-\d{1,2}:\d{2})\b", self.titulo or "")
        return m.group(1) if m else ""

    @property
    def fecha(self) -> date | None:
        """Fecha de uso escrita en claro en el título (no es un dato personal)."""
        m = re.search(r"(\d{4}-\d{2}-\d{2})", self.titulo or "")
        try:
            return date.fromisoformat(m.group(1)) if m else None
        except ValueError:
            return None


BORRADO = "Datos borrados por el bot después de usarlos. Este ticket ya no contiene información."


def excedentes(tickets: list[Issue], por_persona: int = 2, exentos: set[str] | None = None) -> list[tuple[Issue, str]]:
    """Tickets que se pasan del límite por persona (función pura, probada).

    Cuenta por autor (login de GitHub) los tickets abiertos ordenados por número. Se quedan los
    primeros `por_persona`; sobran (a) los que repiten un día que esa persona ya pidió y (b) los que
    exceden el límite. El administrador (`exentos`) y los tickets sin autor no se limitan.
    """
    exentos = {e.lower() for e in (exentos or set())}
    sobran: list[tuple[Issue, str]] = []
    vistos: dict[str, list[Issue]] = {}
    for t in sorted(tickets, key=lambda i: i.numero):
        a = (t.autor or "").lower()
        if not t.abierto or not a or a in exentos or a.endswith("[bot]"):
            continue
        mios = vistos.setdefault(a, [])
        if t.fecha and any(m.fecha == t.fecha for m in mios):
            sobran.append((t, f"ya tienes una solicitud activa para el {t.fecha} (una por día por persona)"))
            continue
        if len(mios) >= por_persona:
            sobran.append((t, f"máximo {por_persona} solicitudes activas por persona; cuando se use o cierres una, vuelve a pedir"))
            continue
        mios.append(t)
    return sobran


def titulo_ticket(fecha: date | str, horario: str, ref: str = "") -> str:
    """Solo datos NO personales: fecha, horario y una referencia aleatoria para seguir el estado."""
    return f"Solicitud de reserva · {fecha} · {horario}" + (f" · ref {ref}" if ref else "")


class GitHubIssues:
    """Lee y actualiza las solicitudes. Errores de red: se registran y no detienen al bot."""

    def __init__(self, repo: str, token: str, log=print, api: str | None = None):
        api = (api or os.getenv("UPB_GH_API") or "https://api.github.com").rstrip("/")  # UPB_GH_API: solo para pruebas
        self.base = f"{api}/repos/{repo}"
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28"})
        self.log = log

    @staticmethod
    def _issue(i: dict) -> Issue:
        return Issue(i["number"], i.get("body") or "", {l["name"] for l in i.get("labels", [])},
                     i.get("title") or "", i.get("state") == "open", ((i.get("user") or {}).get("login") or ""))

    def listar(self) -> list[Issue]:
        r = self.s.get(f"{self.base}/issues", params={"state": "open", "per_page": 100}, timeout=20)
        r.raise_for_status()
        return [self._issue(i) for i in r.json()
                if "pull_request" not in i and MARCADOR in (i.get("body") or "")]

    def obtener(self, numero: int) -> Issue | None:
        """None si el ticket se eliminó o no es un ticket."""
        r = self.s.get(f"{self.base}/issues/{numero}", timeout=20)
        if r.status_code in (404, 410):
            return None
        r.raise_for_status()
        i = r.json()
        return None if "pull_request" in i else self._issue(i)

    def despachar(self, numero: int, ref: str = "main") -> bool:
        """Lanza la corrida AISLADA de este ticket (workflow_dispatch con input ticket)."""
        try:
            self.s.post(f"{self.base}/actions/workflows/reservar.yml/dispatches",
                        json={"ref": ref, "inputs": {"ticket": str(numero)}}, timeout=20).raise_for_status()
            return True
        except requests.RequestException as e:
            self.log(f"No pude lanzar la corrida del ticket #{numero} ({e.__class__.__name__}).")
            return False

    def quitar_etiqueta(self, numero: int, etiqueta: str) -> None:
        try:
            r = self.s.delete(f"{self.base}/issues/{numero}/labels/{etiqueta}", timeout=20)
            if r.status_code not in (200, 404):
                r.raise_for_status()
        except requests.RequestException:
            pass

    def borrar_datos(self, numero: int) -> None:
        self._intentar("PATCH", f"/issues/{numero}", json={"body": BORRADO})

    def _intentar(self, metodo: str, ruta: str, **kw) -> None:
        try:
            self.s.request(metodo, self.base + ruta, timeout=20, **kw).raise_for_status()
        except requests.RequestException as e:
            self.log(f"No pude actualizar la solicitud en GitHub ({e.__class__.__name__}): {ruta}")

    def comentar(self, numero: int, texto: str) -> None:
        self._intentar("POST", f"/issues/{numero}/comments", json={"body": texto})

    def etiquetar(self, numero: int, etiquetas: list[str]) -> None:
        self._intentar("POST", f"/issues/{numero}/labels", json={"labels": etiquetas})

    def cerrar(self, numero: int) -> None:
        self._intentar("PATCH", f"/issues/{numero}", json={"state": "closed"})
