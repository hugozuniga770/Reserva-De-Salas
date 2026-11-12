"""Pruebas del relevo (relevo.py / relevo.yml): el arranque puntual sin depender del cron."""
from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timedelta

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import relevo  # noqa: E402

OBJ, FIN = (18, 45), (21, 15)
VIDA = 335 * 60


def bo(h, m, dia=11):
    return datetime(2026, 11, dia, h, m, tzinfo=relevo.BO)


def test_lanza_a_la_hora_objetivo():
    p = relevo.planear(bo(18, 45), 0, VIDA, OBJ, FIN, lanzado_hoy=False)
    assert p.accion == "lanzar"


def test_relevo_que_despierta_tarde_lanza_de_inmediato():
    """Si GitHub arrancó este relevo a las 19:30 (o el anterior se cortó), no espera a mañana."""
    assert relevo.planear(bo(19, 30), 0, VIDA, OBJ, FIN, False).accion == "lanzar"
    assert relevo.planear(bo(21, 14), 0, VIDA, OBJ, FIN, False).accion == "lanzar"


def test_despues_del_fin_no_lanza_y_apunta_a_manana():
    p = relevo.planear(bo(21, 16), 0, VIDA, OBJ, FIN, False)
    assert p.accion == "relevar"            # mañana 18:45 queda a 21,5 h: no entra en 5 h 35
    assert "12/11 18:45" in p.motivo


def test_no_lanza_dos_veces_el_mismo_dia():
    p = relevo.planear(bo(19, 0), 60, VIDA, OBJ, FIN, lanzado_hoy=True)
    assert p.accion == "relevar"


def test_duerme_hasta_el_objetivo_si_entra_en_su_vida():
    p = relevo.planear(bo(14, 0), 0, VIDA, OBJ, FIN, False)
    assert p.accion == "dormir"
    assert p.segundos == pytest.approx(4 * 3600 + 45 * 60)


def test_pasa_el_relevo_si_el_objetivo_no_entra():
    """A las 12:00 faltan 6 h 45: más que la vida del relevo. Duerme lo que le queda y relanza."""
    p = relevo.planear(bo(12, 0), 0, VIDA, OBJ, FIN, False)
    assert p.accion == "relevar"
    assert p.segundos == pytest.approx(VIDA - relevo.MARGEN)


def test_relevo_avanzado_en_su_vida_no_se_pasa_del_presupuesto():
    """Lleva 5 h corriendo a las 14:00: faltan 4 h 45 al objetivo pero solo le quedan ~34 min."""
    p = relevo.planear(bo(14, 0), 5 * 3600, VIDA, OBJ, FIN, False)
    assert p.accion == "relevar"
    assert p.segundos == pytest.approx(VIDA - 5 * 3600 - relevo.MARGEN)


def test_cadena_cubre_24_horas_sin_huecos():
    """Simula 3 días de relevos encadenados: cada día se lanza exactamente una vez, a las 18:45."""
    ahora = bo(10, 0, dia=8)
    lanzamientos = []
    for _ in range(40):
        inicio = ahora
        # Memoria de la cadena: un relevo nuevo pregunta a GitHub si hoy ya se lanzó (GitHub.lanzada_hoy)
        lanzado_hoy = any(l.date() == ahora.date() for l in lanzamientos)
        while True:
            p = relevo.planear(ahora, (ahora - inicio).total_seconds(), VIDA, OBJ, FIN, lanzado_hoy)
            if p.accion == "lanzar":
                lanzamientos.append(ahora)
                lanzado_hoy = True
                ahora += timedelta(seconds=60)
            elif p.accion == "dormir":
                ahora += timedelta(seconds=p.segundos)
            else:
                ahora += timedelta(seconds=p.segundos + 45)   # 45 s: arranque del siguiente relevo
                break
            if ahora.date() != inicio.date():
                lanzado_hoy = False
        if ahora > bo(10, 0, dia=11):
            break
    dias = {l.date() for l in lanzamientos}
    assert len(lanzamientos) == len(dias) >= 3
    assert all((l.hour, l.minute) == OBJ for l in lanzamientos), lanzamientos


def test_workflow_relevo_bien_configurado():
    yml = (RAIZ / ".github" / "workflows" / "relevo.yml").read_text(encoding="utf-8")
    assert "group: relevo" in yml and "cancel-in-progress: false" in yml   # 1 corriendo + 1 en cola, nunca dos cadenas
    assert "actions: write" in yml
    assert "github.repository == 'hugozuniga770/Reserva-De-Salas'" in yml
    assert "timeout-minutes: 355" in yml and "UPB_RELEVO_MINUTOS: '335'" in yml


def test_reservar_respeta_la_pausa_cuando_lanza_el_relevo():
    yml = (RAIZ / ".github" / "workflows" / "reservar.yml").read_text(encoding="utf-8")
    assert "origen:" in yml
    assert "inputs.origen != 'relevo') || vars.UPB_PAUSADO != '1'" in yml


def test_no_lanza_si_ya_hay_una_reserva_activa(monkeypatch):
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"workflow_runs": [
                {"status": "completed", "display_title": "Tu reserva"},
                {"status": "queued", "display_title": "Solicitud #3"},
                {"status": "in_progress", "display_title": "Tu reserva"},
            ]}
    gh = relevo.GitHub("x/y", "t")
    monkeypatch.setattr(gh.s, "get", lambda *a, **k: Resp())
    assert gh.reserva_activa()
    Resp.json = lambda self: {"workflow_runs": [{"status": "completed", "display_title": "Tu reserva"}]}
    assert not gh.reserva_activa()


def test_lanzada_hoy_recuerda_lo_que_hizo_el_relevo_anterior(monkeypatch):
    """Un relevo que arranca a las 19:35 no relanza si ya hubo una «Tu reserva» a las 18:45 (aunque
    ya haya terminado, p. ej. reservó a las 20:00 y cerró). Una de ayer no cuenta."""
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"workflow_runs": [
                {"status": "completed", "display_title": "Tu reserva", "created_at": "2026-11-11T22:45:10Z"},  # 18:45 BO hoy
                {"status": "completed", "display_title": "Solicitud #4", "created_at": "2026-11-11T22:46:00Z"},
            ]}
    gh = relevo.GitHub("x/y", "t")
    monkeypatch.setattr(gh.s, "get", lambda *a, **k: Resp())
    assert gh.lanzada_hoy(OBJ, ahora=bo(19, 35))
    assert not gh.lanzada_hoy(OBJ, ahora=bo(19, 35, dia=12))
    Resp.json = lambda self: {"workflow_runs": [{"status": "completed", "display_title": "Tu reserva", "created_at": "2026-11-11T20:00:00Z"}]}  # 16:00 BO: cron tardío de antes del objetivo
    assert not gh.lanzada_hoy(OBJ, ahora=bo(19, 35))
