"""
Solicitudes de otros estudiantes: cifrado navegador↔bot, aprobación, auto-aprobación
a las 18:30, prioridad del dueño, cupo, duplicados, privacidad en logs y comentarios.
"""
import base64
import json
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).parent))
import reserva_bot as rb  # noqa: E402
import solicitudes as sol  # noqa: E402
from test_reserva_bot import HOY, config, servidor  # noqa: E402,F401  (fixture)


# ───────────────────────── utilidades ─────────────────────────

def llaves():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = k.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    priv = k.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return base64.b64encode(pub).decode(), base64.b64encode(priv).decode()


PUB, PRIV = llaves()
CLAVE = sol.cargar_clave_privada(PRIV)


def solicitud(nombre="Ana María", apellido="Pérez Soto", codigo="81234", salas=("8", "6"),
              horario="12:15-14:15", fecha=HOY, ntfy="", proposito="Repaso de cálculo"):
    return {"v": 1, "nombre": nombre, "apellido": apellido, "codigo": codigo, "salas": list(salas),
            "horario": horario, "fecha": str(fecha), "ntfy": ntfy, "proposito": proposito}


class FuenteFalsa:
    """Imita los issues de GitHub: un ticket = un issue cifrado de un solo uso."""

    def __init__(self):
        self.issues: dict[int, sol.Issue] = {}
        self.comentarios: dict[int, list[str]] = {}
        self.despachados: list[int] = []

    def agregar(self, numero, datos=None, etiquetas=(), crudo=None, fecha=HOY, horario="12:15-14:15"):
        token = crudo if crudo is not None else sol.cifrar(datos, PUB)
        self.issues[numero] = sol.Issue(numero, f"{sol.MARCADOR}\n\n{token}", set(etiquetas),
                                        sol.titulo_ticket(fecha, horario), True)

    def listar(self):
        return [i for i in self.issues.values() if i.abierto]

    def obtener(self, n):
        return self.issues.get(n)

    def despachar(self, n, ref="main"):
        self.despachados.append(n)
        return True

    def comentar(self, n, t):
        self.comentarios.setdefault(n, []).append(t)

    def etiquetar(self, n, ets):
        self.issues[n].etiquetas |= set(ets)

    def quitar_etiqueta(self, n, e):
        self.issues[n].etiquetas.discard(e)

    def borrar_datos(self, n):
        self.issues[n].cuerpo = sol.BORRADO

    def cerrar(self, n):
        self.issues[n].abierto = False


DIA = lambda: datetime(2026, 10, 22, 19, 10, tzinfo=rb.BO_TZ)    # tras 18:30; servidor ya en el 23
MANIANA = lambda: datetime(2026, 10, 22, 9, 0, tzinfo=rb.BO_TZ)  # antes de 18:30
TARDE = lambda: datetime(2026, 10, 22, 16, 0, tzinfo=rb.BO_TZ)   # 16:00: ya se lanzan los del día siguiente


def ticket(url, fuente, numero, **kw):
    """Corrida AISLADA de un ticket."""
    kw.setdefault("reloj", DIA)
    kw.setdefault("max_segundos", 1)
    return rb.Bot(config(url, **kw), fuente=fuente, clave=CLAVE, ticket=numero)


def principal(url, fuente, **kw):
    """Tu corrida (también lanza las corridas de los tickets listos)."""
    kw.setdefault("reloj", DIA)
    kw.setdefault("max_segundos", 1)
    kw.setdefault("salas", ["8", "6", "15", "3"])
    return rb.Bot(config(url, **kw), fuente=fuente, clave=CLAVE)


# ───────────────────────── corrida aislada de un ticket ─────────────────────────

def test_ticket_reserva_solo_a_su_persona_y_borra_los_datos(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(12, solicitud(salas=("6", "15")), etiquetas={"aprobada", "en-curso"})
    assert ticket(url, f, 12).ejecutar() == 0
    assert [(x["room"], x["first_name"]) for x in est.posts] == [("6", "Ana María")]  # nadie más
    t = f.issues[12]
    assert not t.abierto and "reservada" in t.etiquetas and "en-curso" not in t.etiquetas
    assert t.cuerpo == sol.BORRADO and "upbv1" not in t.cuerpo        # datos borrados tras usarlos
    assert f.comentarios[12][0].startswith("✅ Reservado y verificado: Sala de estudio D")
    assert "Ana" not in f.comentarios[12][0] and "81234" not in f.comentarios[12][0]


def test_ticket_eliminado_termina_sin_hacer_nada(servidor):
    est, url = servidor("normal")
    assert ticket(url, FuenteFalsa(), 99).ejecutar() == 0
    assert est.posts == []


def test_ticket_rechazado_no_reserva(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(5, solicitud(), etiquetas={"rechazada"})
    ticket(url, f, 5).ejecutar()
    assert est.posts == []


def test_ticket_ilegible_se_descarta_y_borra(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(7, crudo="upbv1.AAAA.BBBB.CCCC", etiquetas={"aprobada"})
    ticket(url, f, 7).ejecutar()
    assert not f.issues[7].abierto and "invalida" in f.issues[7].etiquetas
    assert f.issues[7].cuerpo == sol.BORRADO and est.posts == []


def test_ticket_con_codigo_invalido_no_expone_el_dato(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(8, solicitud(codigo="12ab"), etiquetas={"aprobada"})
    ticket(url, f, 8).ejecutar()
    assert not f.issues[8].abierto and "12ab" not in f.comentarios[8][0]


def test_ticket_con_tu_codigo_se_descarta(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(9, solicitud(codigo="95503"), etiquetas={"aprobada"})
    ticket(url, f, 9).ejecutar()
    assert not f.issues[9].abierto and "mismo código" in f.comentarios[9][0] and est.posts == []


def test_ticket_solo_salas_de_estudio(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(4, solicitud(salas=("10", "13")), etiquetas={"aprobada"})
    ticket(url, f, 4).ejecutar()
    assert not f.issues[4].abierto and "sala de estudio" in f.comentarios[4][0]


def test_ticket_de_otro_dia_espera_sin_tocar_nada(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(3, solicitud(fecha=date(2026, 10, 30)), etiquetas={"aprobada"}, fecha=date(2026, 10, 30))
    ticket(url, f, 3, max_segundos=0.4).ejecutar()
    assert est.posts == [] and f.issues[3].abierto and "upbv1" in f.issues[3].cuerpo


def test_ticket_vencido_se_cierra_sin_sala(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(4, solicitud(fecha=date(2026, 10, 20)), etiquetas={"aprobada"}, fecha=date(2026, 10, 20))
    ticket(url, f, 4).ejecutar()
    assert not f.issues[4].abierto and "sin-sala" in f.issues[4].etiquetas and est.posts == []


def test_ticket_oculta_los_datos_en_los_logs_publicos(servidor, capsys):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(12, solicitud(), etiquetas={"aprobada"})
    ticket(url, f, 12).ejecutar()
    lineas = capsys.readouterr().out.splitlines()
    assert {"::add-mask::Ana María Pérez Soto", "::add-mask::81234"} <= set(lineas)
    primera = min(i for i, l in enumerate(lineas) if "81234" in l or "Ana María" in l)
    assert lineas[primera].startswith("::add-mask::")  # nada se imprime antes de ocultarlo


def test_ticket_respeta_tu_sala_favorita_al_abrir(servidor):
    est, url = servidor("normal")
    est.hoy = date(2026, 10, 22)
    est.cambiar_dia_tras_gets = 2                        # la apertura ocurre durante la corrida
    f = FuenteFalsa()
    f.agregar(6, solicitud(salas=("8",)), etiquetas={"aprobada"})
    b = ticket(url, f, 6, max_segundos=0.6)
    b.sala_duenio = "8"
    b.ejecutar()
    assert est.posts == []                               # en los primeros 20 s la F es tuya


def test_tickets_no_se_mezclan_entre_corridas(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(1, solicitud(codigo="11111", salas=("6",)), etiquetas={"aprobada"})
    f.agregar(2, solicitud(nombre="Luis", apellido="Rojas", codigo="22222", salas=("15",)), etiquetas={"aprobada"})
    del f.issues[1]                                      # se elimina el #1 antes de su corrida
    assert ticket(url, f, 1).ejecutar() == 0             # su corrida no encuentra nada
    assert ticket(url, f, 2).ejecutar() == 0             # la del #2 sigue intacta
    assert [x["first_name"] for x in est.posts] == ["Luis"]


# ───────────────────────── tu corrida: solo lanza tickets ─────────────────────────

def test_tu_corrida_nunca_reserva_para_otros(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(12, solicitud(), etiquetas={"aprobada"})
    assert principal(url, f).ejecutar() == 0
    assert [x["first_name"] for x in est.posts] == ["Hugo Rafael"]
    assert f.despachados == [12] and "en-curso" in f.issues[12].etiquetas
    assert "upbv1" in f.issues[12].cuerpo                # tu corrida ni lo descifra ni lo toca


def test_despacho_solo_enruta_numeros_sin_descifrar(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(7, crudo="upbv1.AAAA.BBBB.CCCC", etiquetas={"aprobada"})
    principal(url, f).ejecutar()
    assert f.despachados == [7] and f.issues[7].abierto   # lo valida su propia corrida


def test_pendiente_antes_de_las_18_30_no_se_lanza(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(5, solicitud())
    principal(url, f, reloj=MANIANA).ejecutar()
    assert f.despachados == []


def test_pendiente_se_lanza_sola_despues_de_las_18_30(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(5, solicitud())
    principal(url, f).ejecutar()
    assert f.despachados == [5]


def test_auto_aprobacion_apagada(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(5, solicitud())
    principal(url, f, auto_aprobar=False).ejecutar()
    assert f.despachados == []


def test_rechazados_y_en_curso_no_se_relanzan(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(5, solicitud(), etiquetas={"rechazada"})
    f.agregar(6, solicitud(codigo="66666"), etiquetas={"aprobada", "en-curso"})
    principal(url, f).ejecutar()
    assert f.despachados == []


def test_cupo_por_noche(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    for n in (1, 2, 3):
        f.agregar(n, solicitud(codigo=f"{n}{n}{n}{n}{n}"), etiquetas={"aprobada"})
    principal(url, f, max_personas=3).ejecutar()
    assert f.despachados == [1, 2] and f.issues[3].abierto


def test_pedidos_con_semanas_de_anticipacion(servidor):
    """Se puede pedir desde siempre: se lanza recién el día anterior desde las 15:30."""
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(1, solicitud(fecha=date(2026, 11, 20)), etiquetas={"aprobada"}, fecha=date(2026, 11, 20))
    f.agregar(2, solicitud(codigo="22222", fecha=date(2026, 10, 24)), etiquetas={"aprobada"},
              fecha=date(2026, 10, 24))
    principal(url, f, reloj=MANIANA).ejecutar()
    assert f.despachados == []                           # 09:00: aún no toca ninguno
    principal(url, f, reloj=TARDE).ejecutar()
    assert f.despachados == [2]                          # 16:00: el de mañana sí; el de noviembre espera


def test_dry_run_no_toca_los_tickets(servidor):
    est, url = servidor("normal")
    f = FuenteFalsa()
    f.agregar(12, solicitud(), etiquetas={"aprobada"})
    assert principal(url, f, dry_run=True).ejecutar() == 0
    assert ticket(url, f, 12, dry_run=True).ejecutar() == 0
    assert est.posts == [] and f.comentarios == {} and f.despachados == [] and f.issues[12].abierto


# ───────────────────────── cifrado ─────────────────────────

def test_cifrado_python_ida_y_vuelta():
    assert sol.descifrar(sol.cifrar(solicitud(), PUB), CLAVE)["nombre"] == "Ana María"


@pytest.mark.skipif(not shutil.which("node"), reason="node no instalado")
def test_cifrado_del_navegador_lo_lee_el_bot_y_viceversa():
    js = str(RAIZ / "tests" / "compat_cifrado.js")
    par = json.loads(subprocess.check_output(["node", js, "llaves"], text=True))
    datos = solicitud(nombre="Óscar Ñuflo")
    token = subprocess.check_output(["node", js, "cifrar", par["publica"], json.dumps(datos)], text=True).strip()
    assert sol.descifrar(token, sol.cargar_clave_privada(par["privada"])) == datos
    token_py = sol.cifrar(datos, par["publica"])
    assert json.loads(subprocess.check_output(["node", js, "descifrar", par["privada"], token_py], text=True)) == datos


def test_llave_equivocada_no_descifra():
    _, otra = llaves()
    with pytest.raises(sol.SolicitudInvalida):
        sol.descifrar(sol.cifrar(solicitud(), PUB), sol.cargar_clave_privada(otra))


def test_sin_llave_el_bot_sigue_solo_contigo(monkeypatch):
    for v in ("UPB_GH_TOKEN", "UPB_REPO", "UPB_CLAVE_PRIVADA"):
        monkeypatch.delenv(v, raising=False)
    assert rb.fuente_desde_entorno() == (None, None)


def test_ticket_aprobado_de_noche_no_se_cierra_sin_vigilar(servidor):
    """Caso real (05/11 22:54): se aprueba un ticket para el día siguiente después de las 21:15.
    Su corrida no debe cerrarlo como 'sin sala' tras una sola consulta: lo deja abierto para que
    vuelva a lanzarse, con sus datos intactos."""
    est, url = servidor("normal")
    est.reservar("Otra Persona", "8", "12:15-14:15")
    f = FuenteFalsa()
    f.agregar(1, solicitud(salas=("8",)), etiquetas={"aprobada", "en-curso"})
    noche = lambda: datetime(2026, 10, 22, 22, 54, tzinfo=rb.BO_TZ)  # servidor ya en el 23
    assert ticket(url, f, 1, reloj=noche).ejecutar() == 0
    assert f.issues[1].abierto and "sin-sala" not in f.issues[1].etiquetas
    assert "upbv1" in f.issues[1].cuerpo and est.posts == []


def test_ticket_lanzado_de_noche_con_minutos_vigila_cancelaciones(servidor):
    """Desde el panel, fuera de 15:00–21:15, el ticket se lanza con 'minutos': vigila y toma
    la sala si alguien la libera."""
    est, url = servidor("normal")
    est.reservar("Otra Persona", "8", "12:15-14:15")
    est.liberar_tras_gets = ("8", "12:15-14:15", 4)
    f = FuenteFalsa()
    f.agregar(1, solicitud(salas=("8",)), etiquetas={"aprobada", "en-curso"})
    noche = lambda: datetime(2026, 10, 22, 22, 54, tzinfo=rb.BO_TZ)
    assert ticket(url, f, 1, reloj=noche, hasta_bo="", max_segundos=3).ejecutar() == 0
    assert [x["first_name"] for x in est.posts] == ["Ana María"]
    assert not f.issues[1].abierto and "reservada" in f.issues[1].etiquetas


# ───────────────────────── de punta a punta por HTTP, como en GitHub Actions ─────────────────────────

class _GitHubHTTP:
    """API de GitHub mínima por HTTP: verifica las rutas REALES que usa solicitudes.GitHubIssues."""

    def __init__(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        self.issues, self.llamadas, self.despachos = {}, [], []
        gh = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _resp(self, cod, datos=None):
                cuerpo = b"" if datos is None else json.dumps(datos).encode()
                self.send_response(cod)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def _manejar(self, metodo):
                from urllib.parse import unquote, urlparse
                largo = int(self.headers.get("Content-Length") or 0)
                cuerpo = json.loads(self.rfile.read(largo)) if largo else None
                ruta = urlparse(self.path).path
                gh.llamadas.append((metodo, ruta))
                assert self.headers.get("Authorization") == "Bearer tok-prueba"
                base = "/repos/hugo/Reserva-De-Salas"
                if not ruta.startswith(base):
                    return self._resp(404, {"message": "Not Found"})
                r = ruta[len(base):]
                if r == "/issues" and metodo == "GET":
                    return self._resp(200, [i for i in gh.issues.values() if i["state"] == "open"])
                if r == "/actions/workflows/reservar.yml/dispatches" and metodo == "POST":
                    gh.despachos.append(cuerpo)
                    return self._resp(204)
                partes = r.split("/")  # ['', 'issues', n, ...]
                if len(partes) >= 3 and partes[1] == "issues":
                    n = int(partes[2])
                    i = gh.issues.get(n)
                    if i is None:
                        return self._resp(404, {"message": "Not Found"})
                    resto = "/".join(partes[3:])
                    if resto == "" and metodo == "GET":
                        return self._resp(200, i)
                    if resto == "" and metodo == "PATCH":
                        i.update({k: v for k, v in cuerpo.items() if k in ("body", "state")})
                        return self._resp(200, i)
                    if resto == "comments" and metodo == "POST":
                        i.setdefault("_comentarios", []).append(cuerpo["body"])
                        return self._resp(201, {})
                    if resto == "labels" and metodo == "POST":
                        for e in cuerpo["labels"]:
                            if e not in [x["name"] for x in i["labels"]]:
                                i["labels"].append({"name": e})
                        return self._resp(200, i["labels"])
                    if resto.startswith("labels/") and metodo == "DELETE":
                        e = unquote(resto[len("labels/"):])
                        i["labels"] = [x for x in i["labels"] if x["name"] != e]
                        return self._resp(200, i["labels"])
                return self._resp(404, {"message": f"no simulado {metodo} {r}"})

            def do_GET(self): self._manejar("GET")
            def do_POST(self): self._manejar("POST")
            def do_PATCH(self): self._manejar("PATCH")
            def do_DELETE(self): self._manejar("DELETE")

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}"

    def agregar(self, n, datos, etiquetas, fecha):
        self.issues[n] = {"number": n, "state": "open", "title": sol.titulo_ticket(fecha, "12:15-14:15", "ABC234"),
                          "body": f"{sol.MARCADOR}\n\n{sol.cifrar(datos, PUB)}\n", "labels": [{"name": e} for e in etiquetas]}


def _entorno_actions(monkeypatch, url_upb, gh, **extra):
    """Las mismas variables que pone reservar.yml en GitHub Actions."""
    vars_ = {"UPB_NOMBRE": "Hugo Rafael", "UPB_APELLIDO": "Zúñiga Daza", "UPB_CODIGO": "95503",
             "UPB_SALAS": "8,6,15,3", "UPB_HORARIO": "12:15-14:15", "UPB_DRY_RUN": "0", "UPB_URL": url_upb,
             "UPB_HASTA_BO": "", "UPB_MAX_MINUTOS": "0.1", "UPB_GH_TOKEN": "tok-prueba",
             "UPB_REPO": "hugo/Reserva-De-Salas", "UPB_CLAVE_PRIVADA": PRIV, "UPB_GH_API": gh.url,
             "GITHUB_REF_NAME": "main", "NTFY_TOPIC": ""}
    vars_.update(extra)
    for k, v in vars_.items():
        monkeypatch.setenv(k, v)


def _manana_bo():
    from datetime import timedelta
    return (datetime.now(rb.BO_TZ) + timedelta(days=1)).date()


def test_corrida_de_ticket_completa_por_http(servidor, monkeypatch):
    """Como en Actions con input ticket=12: lee SOLO el #12 por la API, reserva, comenta,
    etiqueta, quita en-curso, borra los datos y cierra. Todo por HTTP."""
    est, url = servidor("normal")
    est.hoy = _manana_bo()
    gh = _GitHubHTTP()
    gh.agregar(12, solicitud(salas=("6",), fecha=est.hoy), {"aprobada", "en-curso"}, est.hoy)
    _entorno_actions(monkeypatch, url, gh, UPB_TICKET="12")
    assert rb.main() == 0
    i = gh.issues[12]
    assert [x["first_name"] for x in est.posts] == ["Ana María"]
    assert i["state"] == "closed" and i["body"] == sol.BORRADO
    assert {x["name"] for x in i["labels"]} == {"aprobada", "reservada"}
    assert i["_comentarios"][0].startswith("✅ Reservado y verificado: Sala de estudio D")
    gh.srv.shutdown()


def test_tu_corrida_lanza_tickets_por_http(servidor, monkeypatch):
    """Como en Actions sin ticket: tu corrida lista los tickets por la API y lanza la corrida
    aislada del aprobado (workflow_dispatch con ticket como texto), sin tocar su contenido."""
    est, url = servidor("normal")
    est.hoy = _manana_bo()
    gh = _GitHubHTTP()
    gh.agregar(7, solicitud(fecha=est.hoy), {"aprobada"}, est.hoy)
    gh.agregar(8, solicitud(codigo="22222", fecha=est.hoy), {"rechazada"}, est.hoy)
    _entorno_actions(monkeypatch, url, gh)
    monkeypatch.setattr(rb.Bot, "en_nucleo_apertura", lambda self, ahora: False)  # independiente de la hora real
    assert rb.main() == 0
    assert gh.despachos == [{"ref": "main", "inputs": {"ticket": "7"}}]
    assert "en-curso" in {x["name"] for x in gh.issues[7]["labels"]} and "upbv1" in gh.issues[7]["body"]
    assert [x["first_name"] for x in est.posts] == ["Hugo Rafael"]
    gh.srv.shutdown()
