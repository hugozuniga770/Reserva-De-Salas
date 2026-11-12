"""Relevo: arranque puntual sin depender del «schedule» de GitHub ni de servicios externos.

Problema: los arranques programados (cron) de GitHub Actions llegan con horas de
retraso (medido del 07 al 11/11/2026: entre 3 y 8 h; el 09 y el 11 ninguna corrida
llegó antes del fin de las 21:15 BO). Los lanzamientos por `workflow_dispatch`, en
cambio, arrancan en segundos.

Solución: una cadena de corridas «relevo» que nunca se corta. Cada relevo vive hasta
~5 h 35 min (GitHub corta a las 6 h); antes de terminar lanza al siguiente relevo. El
relevo que esté despierto a la hora objetivo (def. 18:45 BO) lanza «Tu reserva» con
`workflow_dispatch`, que sí arranca al instante. Si la cadena se corta por lo que sea
(caída de GitHub, pausa, token), los cron de relevo.yml la vuelven a encender en cuanto
GitHub los ejecute, y los cron de reservar.yml siguen como último respaldo.

Garantías:
  * Nunca lanza dos veces: antes de lanzar mira si ya hay una «Tu reserva» en cola o
    corriendo (por ejemplo, si la arrancaste a mano desde el celular).
  * Respeta la pausa del panel: lanza con `origen=relevo` y reservar.yml no arranca
    cuando UPB_PAUSADO = 1.
  * Un relevo que arranca tarde (después del objetivo, antes del fin) lanza de inmediato.

Variables: UPB_RELEVO_BO (hora objetivo, def. "18:45"), UPB_HASTA_BO (fin, def. "21:15"),
UPB_RELEVO_MINUTOS (vida de cada relevo, def. 335), UPB_GH_TOKEN, UPB_REPO.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

BO = timezone(timedelta(hours=-4))           # Bolivia no tiene horario de verano
WF_RESERVA = "reservar.yml"
WF_RELEVO = "relevo.yml"
REPO_AUTORIZADO = "hugozuniga770/Reserva-De-Salas"
MARGEN = 90                                   # s que se reservan para lanzar al sucesor


def log(msg: str) -> None:
    print(f"[{datetime.now(BO):%H:%M:%S} BO] {msg}", flush=True)


def hhmm(texto: str, defecto: str) -> tuple[int, int]:
    t = (texto or defecto).strip()
    h, m = t.split(":")
    return int(h), int(m)


@dataclass
class Plan:
    """Qué hacer ahora. accion: 'lanzar' | 'dormir' | 'relevar'. segundos: cuánto dormir."""
    accion: str
    segundos: float = 0.0
    motivo: str = ""


def planear(ahora: datetime, transcurrido: float, presupuesto: float,
            objetivo: tuple[int, int], fin: tuple[int, int], lanzado_hoy: bool) -> Plan:
    """Función pura (probada en tests/test_relevo.py).

    - Si estamos entre objetivo y fin y hoy no se lanzó: lanzar ya.
    - Si el próximo objetivo entra en lo que le queda de vida a este relevo: dormir hasta él.
    - Si no: dormir lo que quede y pasar el relevo al siguiente.
    """
    hoy_obj = ahora.replace(hour=objetivo[0], minute=objetivo[1], second=0, microsecond=0)
    hoy_fin = ahora.replace(hour=fin[0], minute=fin[1], second=0, microsecond=0)
    if hoy_obj <= ahora < hoy_fin and not lanzado_hoy:
        return Plan("lanzar", 0, f"{ahora:%H:%M} está entre {objetivo[0]:02d}:{objetivo[1]:02d} y el fin")
    proximo = hoy_obj if ahora < hoy_obj else hoy_obj + timedelta(days=1)
    falta = (proximo - ahora).total_seconds()
    queda = presupuesto - transcurrido - MARGEN
    if falta <= queda:
        return Plan("dormir", falta, f"objetivo {proximo:%d/%m %H:%M} entra en este relevo")
    return Plan("relevar", max(0.0, queda), f"objetivo {proximo:%d/%m %H:%M} queda a {falta/3600:.1f} h; paso el relevo")


class GitHub:
    def __init__(self, repo: str, token: str):
        self.base = f"https://api.github.com/repos/{repo}"
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28"})

    def _corridas(self) -> list[dict]:
        try:
            r = self.s.get(f"{self.base}/actions/workflows/{WF_RESERVA}/runs",
                           params={"per_page": 30}, timeout=20)
            r.raise_for_status()
            return r.json().get("workflow_runs", [])
        except requests.RequestException as e:
            log(f"No pude listar corridas ({e.__class__.__name__}); asumo que no hay ninguna.")
            return []

    @staticmethod
    def _es_tuya(run: dict) -> bool:
        return (run.get("display_title") or run.get("name") or "").startswith("Tu reserva")

    def reserva_activa(self) -> bool:
        """¿Ya hay una «Tu reserva» en cola o corriendo? (lanzada a mano, por cron o por otro relevo)."""
        return any(self._es_tuya(r) and r.get("status") in ("queued", "in_progress", "waiting", "pending", "requested")
                   for r in self._corridas())

    def lanzada_hoy(self, objetivo: tuple[int, int], ahora: datetime | None = None) -> bool:
        """¿Alguna «Tu reserva» se creó hoy a partir de la hora objetivo? Es la memoria de la cadena:
        un relevo nuevo no vuelve a lanzar lo que ya lanzó el anterior (ni lo que detuviste a mano)."""
        ahora = ahora or datetime.now(BO)
        desde = ahora.replace(hour=objetivo[0], minute=objetivo[1], second=0, microsecond=0)
        for r in self._corridas():
            if not self._es_tuya(r):
                continue
            try:
                creada = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(BO)
            except (KeyError, ValueError):
                continue
            if creada >= desde:
                return True
        return False

    def lanzar(self, wf: str, inputs: dict | None = None, intentos: int = 3) -> bool:
        for i in range(1, intentos + 1):
            try:
                r = self.s.post(f"{self.base}/actions/workflows/{wf}/dispatches",
                                json={"ref": "main", "inputs": inputs or {}}, timeout=20)
                if r.status_code == 204:
                    return True
                log(f"Lanzar {wf}: HTTP {r.status_code} {r.text[:200]} (intento {i}/{intentos})")
            except requests.RequestException as e:
                log(f"Lanzar {wf}: {e.__class__.__name__} (intento {i}/{intentos})")
            time.sleep(10 * i)
        return False


def main() -> int:
    repo = os.getenv("UPB_REPO") or os.getenv("GITHUB_REPOSITORY") or ""
    if repo and repo.lower() != REPO_AUTORIZADO.lower():
        log("Copia no autorizada: este relevo solo funciona en el repositorio original (ver LICENSE).")
        return 5
    token = os.getenv("UPB_GH_TOKEN", "")
    if not token or not repo:
        log("Faltan UPB_GH_TOKEN / UPB_REPO.")
        return 1
    objetivo = hhmm(os.getenv("UPB_RELEVO_BO", ""), "18:45")
    fin = hhmm(os.getenv("UPB_HASTA_BO", ""), "21:15")
    presupuesto = float(os.getenv("UPB_RELEVO_MINUTOS", "335")) * 60
    gh = GitHub(repo, token)
    inicio = time.monotonic()
    lanzado_hoy = gh.lanzada_hoy(objetivo)
    dia_lanzado = datetime.now(BO).date() if lanzado_hoy else None
    if lanzado_hoy:
        log("Hoy ya se lanzó «Tu reserva» (relevo anterior, cron o a mano): no la repito.")
    log(f"Relevo v1 | objetivo {objetivo[0]:02d}:{objetivo[1]:02d} BO | vida {presupuesto/60:.0f} min")

    while True:
        ahora = datetime.now(BO)
        if dia_lanzado != ahora.date():
            lanzado_hoy = False
        plan = planear(ahora, time.monotonic() - inicio, presupuesto, objetivo, fin, lanzado_hoy)
        log(f"{plan.accion}: {plan.motivo}")
        if plan.accion == "lanzar":
            if gh.reserva_activa():
                log("Ya hay una «Tu reserva» en cola o corriendo: no lanzo otra.")
            elif gh.lanzar(WF_RESERVA, {"origen": "relevo"}):
                log("«Tu reserva» lanzada (arranca en segundos).")
            else:
                log("No pude lanzar «Tu reserva». Los cron de reservar.yml siguen como respaldo.")
            lanzado_hoy, dia_lanzado = True, ahora.date()
            time.sleep(60)
            continue
        if plan.accion == "dormir":
            time.sleep(plan.segundos)
            continue
        # relevar
        time.sleep(plan.segundos)
        if gh.lanzar(WF_RELEVO):
            log("Relevo entregado al siguiente.")
            return 0
        log("No pude lanzar el siguiente relevo; los cron de relevo.yml reencienden la cadena.")
        return 3


if __name__ == "__main__":
    sys.exit(main())
