"""
Pruebas del bot contra:
  1) la página REAL guardada en 'Pagina UPB/pagina_reservas_upb.html'
  2) un servidor falso que imita atari.scz.upb.edu, con escenarios que antes
     producían falsos positivos (el servidor "dice éxito" pero no guarda, se
     corta la conexión, rechaza, otro estudiante gana la carrera…).
Ejecutar:  python -m pytest -q
"""
import json
import sys
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import reserva_bot as rb  # noqa: E402

SALAS = {"15": "Sala de estudio B", "3": "Sala de estudio C", "6": "Sala de estudio D",
         "8": "Sala de estudio F", "9": "Sala de estudio G", "14": "Sala de estudio H",
         "10": "Sala de lectura A", "13": "Sala de lectura D"}
SLOTS = ["7:45-9:45", "10:00-12:00", "12:15-14:15", "14:30-16:30", "16:45-18:45", "19:00-21:00"]
HOY = date(2026, 10, 23)


# ───────────────────────── servidor falso ─────────────────────────

class Estado:
    def __init__(self, modo="normal"):
        self.modo = modo
        self.hoy = HOY
        self.ocupado: dict[str, dict[str, bool]] = {}
        self.eventos: list[dict] = []
        self.posts: list[dict] = []
        self.gets = 0
        self.liberar_tras_gets = None  # (sala, slot, n): se libera después de n GETs
        self.cambiar_dia_tras_gets = None  # n: el servidor pasa al día siguiente tras n GETs
        self.lock = threading.Lock()

    def reservar(self, nombre, sala, slot):
        self.ocupado.setdefault(sala, {})[slot] = True
        ini, fin = slot.split("-")
        self.eventos.append({
            "title": f"{nombre} \u2014 {SALAS[sala]}",
            "start": f"{self.hoy} {int(ini.split(':')[0]):02d}:{ini.split(':')[1]}:00",
            "end": f"{self.hoy} {int(fin.split(':')[0]):02d}:{fin.split(':')[1]}:00",
            "extendedProps": {"slot": slot, "room": SALAS[sala]},
        })

    def html(self, alerta=""):
        opciones = "".join(f'<option value="{k}" data-rid="{k}">\n {v} </option>' for k, v in SALAS.items())
        occ = json.dumps(self.ocupado) if self.ocupado else "[]"
        return f"""<html><body>
<div>Hoy: {self.hoy:%d/%m/%Y}</div>
{alerta}
<form method="POST" action=""><select name="room" id="roomSelect">
<option value="">— Seleccionar —</option>{opciones}</select></form>
<script>
const occupied = {occ};
const slots    = {json.dumps(SLOTS)};
document.addEventListener('DOMContentLoaded', () => {{
  const today = '{self.hoy}';
  const cal = new FullCalendar.Calendar(el, {{
    initialView: 'timeGridDay',
    events: {json.dumps(self.eventos)},
    height: 500
  }});
}});
</script></body></html>"""


def alerta(tipo, texto):
    return f'<div class="alert alert-{tipo}"><i class="fas fa-check"></i> {texto}</div>'


def crear_handler(est: Estado):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _enviar(self, cuerpo, codigo=200):
            datos = cuerpo.encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):
            with est.lock:
                est.gets += 1
                if est.modo == "caido":
                    return self._enviar("Service Unavailable", 503)
                if est.liberar_tras_gets and est.gets > est.liberar_tras_gets[2]:
                    sala, slot, _ = est.liberar_tras_gets
                    est.ocupado.get(sala, {}).pop(slot, None)
                    est.eventos = [e for e in est.eventos
                                   if not (e["extendedProps"]["slot"] == slot and e["extendedProps"]["room"] == SALAS[sala])]
                    est.liberar_tras_gets = None
                if est.cambiar_dia_tras_gets and est.gets > est.cambiar_dia_tras_gets:
                    est.hoy = date.fromordinal(est.hoy.toordinal() + 1)
                    est.ocupado, est.cambiar_dia_tras_gets = {}, None
                if est.modo == "html_roto":
                    return self._enviar("<html><body>Mantenimiento</body></html>")
                self._enviar(est.html())

        def do_POST(self):
            largo = int(self.headers.get("Content-Length", 0))
            f = {k: v[0] for k, v in parse_qs(self.rfile.read(largo).decode()).items()}
            with est.lock:
                est.posts.append(f)
                nombre = f"{f['first_name']} {f['last_name']}"
                sala, slot = f["room"], f["schedule"]
                if est.modo == "miente":  # dice éxito pero no guarda nada
                    return self._enviar(est.html(alerta("success", f"¡Reserva realizada! {slot}")))
                if est.modo == "rechaza":
                    return self._enviar(est.html(alerta("danger", "El código de estudiante no es válido.")))
                if est.modo == "carrera":  # otro estudiante gana justo antes
                    est.reservar("Otra Persona", sala, slot)
                    return self._enviar(est.html(alerta("danger", "Ese horario ya está ocupado.")))
                if est.modo == "corta":  # guarda pero se cae la conexión sin responder
                    est.reservar(nombre, sala, slot)
                    self.close_connection = True
                    self.connection.shutdown(2)
                    return
                if (est.ocupado.get(sala) or {}).get(slot):
                    return self._enviar(est.html(alerta("danger", "Ese horario ya está ocupado.")))
                est.reservar(nombre, sala, slot)
                self._enviar(est.html(alerta("success", f"¡Reserva realizada! Sala reservada para hoy en el horario {slot}.")))
    return H


@pytest.fixture
def servidor():
    creados = []

    def _crear(modo="normal"):
        est = Estado(modo)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), crear_handler(est))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        creados.append(srv)
        return est, f"http://127.0.0.1:{srv.server_port}/student_reservation.php"
    yield _crear
    for s in creados:
        s.shutdown()


def config(url, **kw):
    base = dict(nombre="Hugo Rafael", apellido="Zúñiga Daza", codigo="95503", salas=["8"],
                horario="12:15-14:15", url=url, max_segundos=3, intervalo=0.05, intervalo_rafaga=0.02,
                intervalo_espera=0.05, pausa_verificacion=0.02,
                reloj=lambda: datetime(2026, 10, 23, 9, 0, tzinfo=rb.BO_TZ))  # 09:00 BO, lejos de la apertura
    base.update(kw)
    return rb.Config(**base)


# ───────────────────────── página real ─────────────────────────

def test_parsea_pagina_real_guardada():
    ruta = RAIZ / "Pagina UPB" / "pagina_reservas_upb.html"
    if not ruta.exists():
        pytest.skip("no está la página guardada")
    p = rb.parsear(ruta.read_text(encoding="utf-8"))
    assert p.salas["8"] == "Sala de estudio F" and p.salas["15"] == "Sala de estudio B"
    assert p.horarios == SLOTS
    assert p.hoy == date(2026, 10, 2)
    assert not rb.sala_libre(p, "8", "12:15-14:15")  # en esa copia la Sala F estaba llena
    assert len(p.eventos) > 10 and all("extendedProps" in e for e in p.eventos)


def test_ids_del_formulario_son_md5_del_horario():
    import hashlib
    ids = {"7:45-9:45": "94b8b48865360042a741a450c6441be0", "12:15-14:15": "b0030e1d389405aae784568ad8e26553",
           "19:00-21:00": "e93ad1f8c976ce25fcaaa7539e2233dd"}
    for slot, id_ in ids.items():
        assert hashlib.md5(slot.encode()).hexdigest() == id_


@pytest.mark.parametrize("entrada,esperado", [("12:15-14:15", "12:15-14:15"), ("07:45 – 09:45", "7:45-9:45"),
                                              ("19:00 - 21:00", "19:00-21:00")])
def test_normaliza_horario(entrada, esperado):
    assert rb.normalizar_horario(entrada) == esperado


def test_nombre_con_y_sin_tildes_coincide():
    cfg = config("x")
    assert rb.normalizar("Hugo Rafael Zuñiga Daza — Sala F").startswith(cfg.clave_nombre)


# ───────────────────────── escenarios ─────────────────────────

def test_reserva_normal_se_confirma(servidor):
    est, url = servidor("normal")
    assert rb.Bot(config(url)).ejecutar() == 0
    assert len(est.posts) == 1
    assert est.posts[0] == {"room": "8", "first_name": "Hugo Rafael", "last_name": "Zúñiga Daza", "code": "95503",
                            "schedule": "12:15-14:15", "purpose": "Estudio académico"}
    assert est.eventos[0]["title"].startswith("Hugo Rafael Zúñiga Daza")


def test_FALSO_POSITIVO_servidor_dice_exito_pero_no_guarda(servidor, capsys):
    est, url = servidor("miente")
    codigo = rb.Bot(config(url, max_segundos=1)).ejecutar()
    salida = capsys.readouterr().out
    assert "NO aparece en el calendario" in salida
    assert "Reserva confirmada" not in salida and "RESERVA CONFIRMADA" not in salida
    assert "no se reservó nada" in salida
    assert codigo == 0 and len(est.posts) >= 1


def test_conexion_cortada_pero_reserva_entro_se_detecta(servidor):
    est, url = servidor("corta")
    assert rb.Bot(config(url)).ejecutar() == 0
    assert len(est.posts) == 1  # no reenvía: verificó que ya era suya


def test_rechazo_repetido_termina_con_error(servidor, capsys):
    est, url = servidor("rechaza")
    assert rb.Bot(config(url, max_rechazos=3)).ejecutar() == rb.EXIT_RECHAZOS
    assert "El código de estudiante no es válido" in capsys.readouterr().out
    assert len(est.posts) == 3


def test_carrera_perdida_no_es_exito(servidor, capsys):
    est, url = servidor("carrera")
    rb.Bot(config(url, max_segundos=0.5)).ejecutar()
    salida = capsys.readouterr().out
    assert "RESERVA CONFIRMADA" not in salida and "Reserva confirmada" not in salida


def test_ya_tenia_reserva_no_envia_nada(servidor, capsys):
    est, url = servidor("normal")
    est.reservar("Hugo Rafael Zuñiga Daza", "15", "12:15-14:15")  # hecha a mano, sin tilde, otra sala
    assert rb.Bot(config(url, max_segundos=30)).ejecutar() == 0
    assert est.posts == []
    assert "Ya tenías la reserva" in capsys.readouterr().out


def test_ocupada_no_envia(servidor):
    est, url = servidor("normal")
    est.reservar("Otra Persona", "8", "12:15-14:15")
    rb.Bot(config(url, max_segundos=0.4)).ejecutar()
    assert est.posts == []


def test_se_libera_y_la_toma(servidor):
    est, url = servidor("normal")
    est.reservar("Otra Persona", "8", "12:15-14:15")
    est.liberar_tras_gets = ("8", "12:15-14:15", 5)
    assert rb.Bot(config(url)).ejecutar() == 0
    assert len(est.posts) == 1 and est.eventos[-1]["title"].startswith("Hugo Rafael")


def test_salas_de_respaldo_en_orden(servidor):
    est, url = servidor("normal")
    est.reservar("Otra Persona", "8", "12:15-14:15")
    assert rb.Bot(config(url, salas=["8", "9", "14"])).ejecutar() == 0
    assert [p["room"] for p in est.posts] == ["9"]


def test_orden_preferido_f_d_b_c_solo_salas_de_estudio(servidor):
    """F, D, B, C — todas 'de estudio'. Toma la primera libre en ese orden,
    saltándose las tres primeras que están ocupadas."""
    est, url = servidor("normal")
    for sala in ("8", "6", "15"):
        est.reservar("Otra Persona", sala, "12:15-14:15")
    orden = ["8", "6", "15", "3"]
    assert rb.Bot(config(url, salas=orden)).ejecutar() == 0
    assert [p["room"] for p in est.posts] == ["3"]
    assert est.eventos[-1]["title"] == "Hugo Rafael Zúñiga Daza \u2014 Sala de estudio C"


def test_defaults_de_ritmo_no_son_de_flood():
    cfg = rb.Config(nombre="x", apellido="y", codigo="1", salas=["8"], horario="12:15-14:15")
    assert cfg.intervalo == 2.0
    assert cfg.intervalo_medio == 1.0
    assert cfg.intervalo_rafaga == 0.25  # ~4 req/s máximo, nunca "por milisegundo"
    assert cfg.intervalo_espera == 30.0


def test_salas_por_defecto_desde_entorno_es_fdbc_sin_lectura(monkeypatch):
    monkeypatch.setenv("UPB_NOMBRE", "Hugo Rafael")
    monkeypatch.setenv("UPB_APELLIDO", "Zúñiga Daza")
    monkeypatch.setenv("UPB_CODIGO", "95503")
    assert rb.Config.desde_entorno().salas == ["8", "6", "15", "3"]


def test_nucleo_y_banda_de_apertura():
    bot = rb.Bot(config("http://x"))
    # núcleo: ±15 min de las 20:00
    assert bot.en_nucleo_apertura(datetime(2026, 10, 23, 19, 59, tzinfo=rb.BO_TZ))
    assert bot.en_nucleo_apertura(datetime(2026, 10, 23, 20, 10, tzinfo=rb.BO_TZ))
    assert not bot.en_nucleo_apertura(datetime(2026, 10, 23, 19, 30, tzinfo=rb.BO_TZ))
    # banda ancha: 19:00-21:00, como pediste
    assert bot.en_banda_apertura(datetime(2026, 10, 23, 19, 0, tzinfo=rb.BO_TZ))
    assert bot.en_banda_apertura(datetime(2026, 10, 23, 19, 30, tzinfo=rb.BO_TZ))  # banda, no núcleo
    assert bot.en_banda_apertura(datetime(2026, 10, 23, 21, 0, tzinfo=rb.BO_TZ))
    assert not bot.en_banda_apertura(datetime(2026, 10, 23, 18, 50, tzinfo=rb.BO_TZ))
    assert not bot.en_banda_apertura(datetime(2026, 10, 23, 21, 10, tzinfo=rb.BO_TZ))


def test_backoff_mas_corto_dentro_de_la_banda():
    assert rb.Bot.backoff(errores_seguidos=4, intervalo=2.0, en_banda=True) == 8.0
    assert rb.Bot.backoff(errores_seguidos=4, intervalo=2.0, en_banda=False) == 32.0
    assert rb.Bot.backoff(errores_seguidos=10, intervalo=2.0, en_banda=False) == 60.0


def test_pagina_rota_nunca_envia(servidor):
    est, url = servidor("html_roto")
    assert rb.Bot(config(url, max_segundos=0.5)).ejecutar() == rb.EXIT_SITIO
    assert est.posts == []


def test_sitio_caido(servidor):
    est, url = servidor("caido")
    assert rb.Bot(config(url, max_segundos=0.5)).ejecutar() == rb.EXIT_SITIO


def test_horario_pasado_no_envia(servidor):
    est, url = servidor("normal")
    tarde = lambda: datetime(2026, 10, 23, 15, 0, tzinfo=rb.BO_TZ)  # 15:00, el 12:15-14:15 ya pasó
    assert rb.Bot(config(url, reloj=tarde, max_segundos=30)).ejecutar() == 0
    assert est.posts == []


def test_tras_las_20_el_servidor_ya_es_manana_y_reserva(servidor):
    est, url = servidor("normal")
    est.hoy = date(2026, 10, 23)
    noche = lambda: datetime(2026, 10, 22, 20, 1, tzinfo=rb.BO_TZ)  # local 22/10, servidor 23/10
    assert rb.Bot(config(url, reloj=noche)).ejecutar() == 0
    assert len(est.posts) == 1


def test_dry_run_no_envia(servidor):
    est, url = servidor("normal")
    assert rb.Bot(config(url, dry_run=True)).ejecutar() == 0
    assert est.posts == []


def test_sala_inexistente_es_error_de_config(servidor):
    est, url = servidor("normal")
    assert rb.Bot(config(url, salas=["99"])).ejecutar() == rb.EXIT_CONFIG


def test_config_desde_entorno(monkeypatch):
    monkeypatch.setenv("UPB_NOMBRE", "Hugo Rafael")
    monkeypatch.setenv("UPB_APELLIDO", "Zúñiga Daza")
    monkeypatch.setenv("UPB_CODIGO", "95503")
    monkeypatch.setenv("UPB_SALAS", "8, 9")
    monkeypatch.setenv("UPB_HORARIO", "07:45 – 09:45")
    cfg = rb.Config.desde_entorno()
    assert cfg.salas == ["8", "9"] and cfg.horario == "7:45-9:45" and cfg.codigo_oculto == "95***"
    monkeypatch.delenv("UPB_CODIGO")
    with pytest.raises(ValueError):
        rb.Config.desde_entorno()


def test_espera_la_apertura_de_las_20_y_reserva_el_dia_siguiente(servidor, capsys):
    est, url = servidor("normal")
    est.reservar("Hugo Rafael Zuñiga Daza", "8", "12:15-14:15")  # ya tiene la de hoy (23/10)
    est.cambiar_dia_tras_gets = 8                                   # a las 20:00 el servidor pasa al 24/10
    en_ventana = lambda: datetime(2026, 10, 23, 19, 59, tzinfo=rb.BO_TZ)
    assert rb.Bot(config(url, reloj=en_ventana, max_segundos=5)).ejecutar() == 0
    assert len(est.posts) == 1 and est.hoy == date(2026, 10, 24)
    assert "Ya tenías la reserva" in capsys.readouterr().out
