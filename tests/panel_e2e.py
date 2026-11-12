"""
Prueba de punta a punta del panel (docs/index.html) en Chromium real, con un GitHub falso.
Uso:  python tests/panel_e2e.py [carpeta_capturas]
Verifica: cifrado desde la página → descifrado en el bot, acciones del administrador,
guardado de ajustes, creación de llave y que no haya errores de JavaScript.
"""
import base64
import json
import os
import re
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import solicitudes as sol  # noqa: E402

CAPTURAS = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/capturas")
CAPTURAS.mkdir(parents=True, exist_ok=True)
REPO = "hugozuniga770/Reserva-De-Salas"

k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUB = base64.b64encode(k.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
PRIV = base64.b64encode(k.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())).decode()
CLAVE = sol.cargar_clave_privada(PRIV)


def ticket(numero, fecha, etiquetas=(), estado="open", ref="ABC234", nombre="Ana María", codigo="81234", salas=("6", "15")):
    datos = {"v": 1, "nombre": nombre, "apellido": "Pérez Soto", "codigo": codigo, "proposito": "Repaso de cálculo",
             "horario": "12:15-14:15", "salas": list(salas), "fecha": fecha, "ntfy": ""}
    return {"number": numero, "title": sol.titulo_ticket(fecha, "12:15-14:15", ref, list(salas)),
            "body": f"{sol.MARCADOR}\nSolicitud cifrada.\n\n{sol.cifrar(datos, PUB)}\n", "state": estado,
            "labels": [{"name": e} for e in etiquetas], "user": {"login": "ana-upb"}}


def refs_propias(pag):
    """Referencias guardadas en el teléfono simulado (localStorage del panel)."""
    return [x.get("ref") for x in pag.evaluate('() => JSON.parse(localStorage.getItem("upb_mis_tickets") || "[]")') if x.get("ref")]


class GitHubFalso:
    def __init__(self):
        self.issues = {12: ticket(12, "2026-11-06", ("aprobada", "en-curso"), ref="K7X2QF"),
                       13: ticket(13, "2026-11-10", (), ref="M4P9RT", nombre="Luis", codigo="22222", salas=("8",)),
                       9: ticket(9, "2026-11-03", ("reservada",), estado="closed", ref="Z9Y8W7"),
                       # jueves 12: tres solicitudes = cupo de la noche (4 personas con el dueño) → el calendario lo cierra
                       14: ticket(14, "2026-11-12", ("aprobada",), ref="A1B2C3", nombre="Carla", codigo="33331"),
                       15: ticket(15, "2026-11-12", (), ref="D4E5F6", nombre="Diego", codigo="33332"),
                       16: ticket(16, "2026-11-12", (), ref="G7H8J9", nombre="Elena", codigo="33333")}
        self.issues[9]["body"] = sol.BORRADO
        self.comentarios = {9: [{"user": {"login": "github-actions[bot]"}, "body": "✅ Reservado y verificado: Sala de estudio D · 12:15-14:15 · 2026-11-03"}]}
        self.runs = [
            {"id": 501, "display_title": "Solicitud #12", "status": "in_progress", "conclusion": None, "event": "workflow_dispatch",
             "run_started_at": "2026-11-05T22:40:00Z", "created_at": "2026-11-05T22:40:00Z", "html_url": "https://github.com/x/runs/501"},
            {"id": 500, "display_title": "Tu reserva", "status": "completed", "conclusion": "success", "event": "schedule",
             "run_started_at": "2026-11-04T22:41:00Z", "created_at": "2026-11-04T22:41:00Z", "html_url": "https://github.com/x/runs/500"},
            # corrida fantasma: GitHub la crea fallida en cada push mientras el workflow es inválido
            {"id": 400, "display_title": "Update reservar.yml", "status": "completed", "conclusion": "failure", "event": "push",
             "run_started_at": "2026-11-05T01:56:00Z", "created_at": "2026-11-05T01:56:00Z", "html_url": "https://github.com/x/runs/400"},
        ]
        self.resultado_runs = {500: "reservada", 501: None}
        self.variables = {"UPB_SALAS": "8,6,15,3", "UPB_HORARIO": "12:15-14:15"}
        self.contenido = {}
        self.despachos, self.llamadas = [], []

    def responder(self, metodo, ruta, consulta, cuerpo):
        self.llamadas.append((metodo, ruta))
        b = f"/repos/{REPO}"
        if not ruta.startswith(b):
            return 404, {"message": "Not Found"}
        r = ruta[len(b):]
        if r == "" and metodo == "GET":
            return 200, {"full_name": REPO}
        if r == "/actions/workflows/reservar.yml/runs":
            return 200, {"workflow_runs": self.runs}
        if r == "/actions/workflows/reservar.yml":
            return 200, {"id": 1}
        if r == "/actions/workflows/reservar.yml/dispatches" and metodo == "POST":
            # Igual que GitHub: el workflow debe ser válido y las entradas, conocidas y de texto.
            permitidas = {"ticket", "salas", "horario", "minutos", "dry_run"}
            entradas = cuerpo.get("inputs", {})
            if cuerpo.get("ref") != "main" or set(entradas) - permitidas or \
                    not all(isinstance(v, str) for v in entradas.values()):
                return 422, {"message": f"Entradas no válidas: {entradas}"}
            self.despachos.append(entradas)
            return 204, None
        m = re.fullmatch(r"/actions/runs/(\d+)/jobs", r)
        if m:
            codigo = self.resultado_runs.get(int(m.group(1)))
            pasos = [{"name": "Reservar (con verificación)", "conclusion": "success"}] + [
                {"name": f"Resultado: {c}", "conclusion": "success" if c == codigo else "skipped"}
                for c in ("reservada", "ya-la-tenia", "no-se-libero", "nada", "prueba", "error")]
            return 200, {"jobs": [{"steps": pasos}]}
        m = re.fullmatch(r"/actions/runs/(\d+)/cancel", r)
        if m:
            return 202, {}
        if r == "/actions/variables" and metodo == "GET":
            return 200, {"variables": [{"name": n, "value": v} for n, v in self.variables.items()]}
        if r == "/actions/variables" and metodo == "POST":
            self.variables[cuerpo["name"]] = cuerpo["value"]
            return 201, {}
        m = re.fullmatch(r"/actions/variables/(\w+)", r)
        if m:
            if metodo == "PATCH":
                self.variables[m.group(1)] = cuerpo["value"]
            elif metodo == "DELETE":
                self.variables.pop(m.group(1), None)
            return 204, None
        if r == "/issues" and metodo == "GET":
            estado = consulta.get("state", ["open"])[0]
            l = [i for i in self.issues.values() if estado == "all" or i["state"] == estado]
            return 200, sorted(l, key=lambda i: -i["number"])
        if r == "/issues" and metodo == "POST":
            n = max(self.issues) + 1
            self.issues[n] = {"number": n, "title": cuerpo["title"], "body": cuerpo["body"], "state": "open",
                              "labels": [{"name": e} for e in cuerpo.get("labels", [])], "user": {"login": "hugozuniga770"}}
            return 201, self.issues[n]
        m = re.fullmatch(r"/issues/(\d+)(/.*)?", r)
        if m:
            n, resto = int(m.group(1)), m.group(2) or ""
            i = self.issues.get(n)
            if i is None:
                return 404, {"message": "Not Found"}
            if resto == "" and metodo == "PATCH":
                i.update({k: v for k, v in cuerpo.items() if k in ("body", "state")})
                return 200, i
            if resto == "/labels" and metodo == "POST":
                for e in cuerpo["labels"]:
                    if e not in [x["name"] for x in i["labels"]]:
                        i["labels"].append({"name": e})
                return 200, i["labels"]
            ml = re.fullmatch(r"/labels/(.+)", resto)
            if ml and metodo == "DELETE":
                i["labels"] = [x for x in i["labels"] if x["name"] != unquote(ml.group(1))]
                return 200, i["labels"]
            if resto == "/comments":
                if metodo == "POST":
                    self.comentarios.setdefault(n, []).append({"user": {"login": "hugozuniga770"}, "body": cuerpo["body"]})
                    return 201, {}
                return 200, self.comentarios.get(n, [])
        if r == "/contents/docs":
            return 200, []
        m = re.fullmatch(r"/contents/docs/([\w.]+)", r)
        if m:
            nombre = m.group(1)
            if metodo == "PUT":
                self.contenido[nombre] = base64.b64decode(cuerpo["content"]).decode("utf-8").strip()
                return 201, {}
            if nombre in self.contenido:
                return 200, {"sha": "abc"}
            return 404, {"message": "Not Found"}
        return 404, {"message": f"Ruta no simulada: {metodo} {r}"}


def servir_docs():
    class Silencioso(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Silencioso, directory=str(RAIZ / "docs")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/"


def main():
    gh = GitHubFalso()
    srv, base = servir_docs()
    errores = []
    resultados = {}

    def enrutar(route):
        req = route.request
        u = urlparse(req.url)
        if u.hostname == "api.github.com":
            cuerpo = json.loads(req.post_data) if req.post_data else None
            st, d = gh.responder(req.method, u.path, parse_qs(u.query), cuerpo)
            return route.fulfill(status=st, body="" if d is None else json.dumps(d), headers={"Content-Type": "application/json"})
        if u.path.endswith("clave_publica.txt"):
            txt = gh.contenido.get("clave_publica.txt", PUB)
            return route.fulfill(status=200, body=txt + "\n", headers={"Content-Type": "text/plain"})
        if u.hostname == "copia.example":  # alguien publicó una copia en otro dominio
            ruta = RAIZ / "docs" / (u.path.lstrip("/") or "index.html")
            if ruta.is_file():
                tipo = "text/html" if ruta.suffix == ".html" else "application/javascript" if ruta.suffix == ".js" else "text/plain"
                return route.fulfill(status=200, body=ruta.read_bytes(), headers={"Content-Type": tipo})
            return route.fulfill(status=404, body="")
        if u.hostname not in ("127.0.0.1",):
            return route.abort()  # fuentes y logo externos: sin red en la prueba
        return route.continue_()

    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="es-BO")
        ctx.route("**/*", enrutar)
        pag = ctx.new_page()
        pag.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))
        pag.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errores.append(f"console: {m.text}"))
        pag.clock.set_fixed_time("2026-11-05T19:20:00-04:00")  # 19:20 en Bolivia

        # ── 1. Página pública: pedir sala ──
        pag.goto(base + "#pedir")
        pag.wait_for_selector("#t-nombre")
        pag.screenshot(path=CAPTURAS / "01-pedir.png", full_page=True)
        # Plazos (19:20: ya pasó el plazo de las 18:30 para el viernes 6, todavía no abre)
        pag.wait_for_selector("text=Ya pasó el plazo para el vie. 6 de noviembre")
        pag.wait_for_selector("text=no disponible (reservada por el servicio)")
        clase = lambda etiqueta: pag.get_attribute(f'button[aria-label^="{etiqueta}"]', "class") or ""
        assert "cancel" in clase("jue. 5 de noviembre"), "hoy ya está abierto: solo cancelaciones"
        assert "tarde" in clase("vie. 6 de noviembre"), "mañana: pasó el plazo"
        assert "tarde" not in clase("lun. 9 de noviembre") and "cancel" not in clase("lun. 9 de noviembre")
        # Cupos: el jueves 12 ya tiene 3 solicitudes (cupo lleno) → rayado y deshabilitado; el martes 10 tiene 1 → "quedan 2"
        assert "lleno" in clase("jue. 12 de noviembre") and pag.is_disabled('button[aria-label^="jue. 12 de noviembre"]'), "día lleno debe cerrarse"
        assert "poco" in clase("mar. 10 de noviembre") and pag.get_attribute('button[aria-label^="mar. 10 de noviembre"]', "data-quedan") == "2 libres"
        pag.wait_for_selector("text=Tienes 0 de 2 solicitudes activas")
        # Colisión de primera sala: el viernes 6 ya tiene a Ana con D de 1ª → la Sala D avisa «ya pedida de 1ª»
        pag.click('button[aria-label^="vie. 6 de noviembre"]')
        pag.wait_for_selector("text=ya pedida de 1ª")
        pag.click('button[aria-label^="vie. 6 de noviembre"]')
        assert pag.query_selector("text=ya pedida de 1ª") is None
        resultados["cupos_en_calendario"] = "OK"
        # Sala F bloqueada solo de 12:15 a 14:15
        f_boton = '.sala-opcion[aria-label^="Sala de estudio F"], .sala-opcion:has-text("Sala F")'
        assert pag.is_disabled(f_boton), "la F de 12:15 debe estar bloqueada"
        pag.click("text=10:00 – 12:00")
        assert not pag.is_disabled(f_boton), "la F a otra hora sí se puede"
        pag.click("text=12:15 – 14:15")
        assert pag.is_disabled(f_boton)
        resultados["plazos_y_bloqueo"] = "OK"
        pag.fill("#t-nombre", "Ana María")
        pag.fill("#t-apellido", "Pérez Soto")
        pag.fill("#t-codigo", "81234")
        pag.click("text=Sala D")
        pag.click("text=Sala B")
        pag.click('button[aria-label^="vie. 6 de noviembre"]')
        pag.click('button[aria-label^="lun. 9 de noviembre"]')
        assert pag.is_disabled('button[aria-label^="dom. 8 de noviembre"]'), "los domingos deben estar bloqueados"
        pag.check("#t-ok")
        pag.click("text=Preparar 2 solicitudes")
        pag.wait_for_selector("text=Marca que entiendes que esos días no tienen garantía")  # el viernes llegó tarde
        pag.check("#t-riesgo")
        pag.screenshot(path=CAPTURAS / "02-pedir-lleno.png", full_page=True)
        pag.click("text=Preparar 2 solicitudes")
        pag.wait_for_selector("text=2 solicitudes listas")
        assert pag.input_value("#t-codigo") == "", "el código debe borrarse del formulario"
        enlaces = pag.eval_on_selector_all('a[href^="https://github.com/"][href*="issues/new"]', "as => as.map(a => a.href)")
        assert len(enlaces) == 2, enlaces
        q = parse_qs(urlparse(enlaces[0]).query)
        titulo, cuerpo = q["title"][0], q["body"][0]
        assert "2026-11-06" in titulo and "Ana" not in titulo and "81234" not in titulo, titulo
        assert "salas D,B" in titulo, "las salas van en claro en el título (no son dato personal); nombre y código no"
        assert "81234" not in cuerpo and "Ana" not in cuerpo, "el cuerpo solo debe llevar datos cifrados"
        datos = sol.descifrar(cuerpo, CLAVE)  # ← el bot puede leer lo que cifró el navegador
        assert datos["codigo"] == "81234" and datos["salas"] == ["6", "15"] and datos["fecha"] == "2026-11-06", datos
        resultados["cifrado_pagina_a_bot"] = "OK"
        mias = pag.evaluate("JSON.parse(localStorage.getItem('upb_mis_tickets'))")
        assert all(set(x) == {"ref", "fecha", "horario"} for x in mias), "en el teléfono solo se guardan referencias, no datos"
        pag.screenshot(path=CAPTURAS / "03-pedir-listo.png", full_page=True)
        # Límite por persona: con el ticket 13 (ref M4P9RT) como propio, el martes 10 queda marcado "tuyo"
        # y, con 2 refs activas más de esta misma pantalla, pedir un tercer día se rechaza.
        pag.evaluate("""() => { const m = JSON.parse(localStorage.getItem("upb_mis_tickets") || "[]"); m.push({ref: "M4P9RT", fecha: "2026-11-10", horario: "12:15-14:15"}); localStorage.setItem("upb_mis_tickets", JSON.stringify(m)); }""")
        gh.issues[20] = ticket(20, "2026-11-09", (), ref=refs_propias(pag)[0] if refs_propias(pag) else "QQQQQQ")
        pag.goto(base + "#estado"); pag.goto(base + "#pedir"); pag.wait_for_selector("#t-nombre")
        assert "mio" in clase("mar. 10 de noviembre") and pag.is_disabled('button[aria-label^="mar. 10 de noviembre"]'), "día ya pedido por esta persona"
        pag.wait_for_selector("text=Tienes 2 de 2 solicitudes activas")
        pag.fill("#t-nombre", "Ana María"); pag.fill("#t-apellido", "Pérez Soto"); pag.fill("#t-codigo", "81234")
        pag.click("text=Sala D"); pag.click('button[aria-label^="mié. 11 de noviembre"]'); pag.check("#t-ok")
        pag.click("text=Preparar solicitud")
        pag.wait_for_selector("text=Máximo 2 solicitudes activas por persona")
        resultados["limite_por_persona"] = "OK"
        del gh.issues[20]

        # ── 2. Estado público ──
        pag.evaluate("localStorage.setItem('upb_mis_tickets', JSON.stringify([{ref:'K7X2QF'},{ref:'Z9Y8W7'},{ref:'M4P9RT'}]))")
        pag.goto(base + "#estado")
        pag.wait_for_selector("text=En curso: el bot está vigilando")
        pag.wait_for_selector("text=Reservada")
        pag.click("text=Ver resultado")
        pag.wait_for_selector("text=Reservado y verificado: Sala de estudio D")
        pag.screenshot(path=CAPTURAS / "04-estado.png", full_page=True)
        resultados["estado_publico"] = "OK"

        # ── 3. Administrador ──
        pag.evaluate(f"""localStorage.setItem('upb_token','github_pat_prueba');
                         localStorage.setItem('upb_privada','{PRIV}');
                         localStorage.setItem('upb_publica','{PUB}');
                         localStorage.setItem('upb_nombre_mostrar','Hugo Zúñiga')""")
        pag.goto(base + "#inicio")
        pag.wait_for_selector("text=El bot no está corriendo")  # 19:20 sin corrida tuya → alerta roja
        pag.wait_for_selector("text=Tu última corrida:")
        assert pag.locator(".alerta-ok", has_text="Reservada ✅").count() == 1, "debe decir cómo terminó tu última corrida"
        assert pag.locator(".items li", has_text="Tu reserva").locator("text=Reservada ✅").count() == 1
        assert pag.locator(".items li", has_text="Solicitud #12").locator("text=En progreso: vigilando").count() == 1
        assert pag.locator("text=Update reservar.yml").count() == 0, "las corridas fantasma de push no se muestran"
        resultados["resultado_de_cada_corrida"] = "OK"
        pag.screenshot(path=CAPTURAS / "05-inicio-alerta.png", full_page=True)
        pag.click("text=Arrancarlo ahora")
        pag.wait_for_selector("text=Bot lanzado")
        assert gh.despachos[-1] == {}, gh.despachos
        pag.click("text=Probar sin reservar")
        pag.wait_for_selector("text=Prueba lanzada")
        assert gh.despachos[-1] == {"dry_run": "true"}, gh.despachos
        resultados["arrancar_desde_alerta"] = "OK"
        # Carril con una corrida tuya corriendo y otra más nueva en cola: debe decir «Vigilando»
        gh.runs[:0] = [
            {"id": 601, "display_title": "Tu reserva", "status": "queued", "conclusion": None, "event": "schedule",
             "run_started_at": None, "created_at": "2026-11-05T22:41:00Z", "html_url": "https://github.com/x/runs/601"},
            {"id": 600, "display_title": "Tu reserva", "status": "in_progress", "conclusion": None, "event": "schedule",
             "run_started_at": "2026-11-05T19:47:00Z", "created_at": "2026-11-05T19:47:00Z", "html_url": "https://github.com/x/runs/600"}]
        pag.goto(base + "#estado")
        pag.goto(base + "#inicio")
        pag.wait_for_selector("text=Vigilando")
        pag.click("text=Detener tu corrida")
        pag.wait_for_selector("text=Corrida detenida")
        assert ("POST", f"/repos/{REPO}/actions/runs/600/cancel") in gh.llamadas, "debe detener la que corre, no la de la cola"
        del gh.runs[:2]
        resultados["corriendo_vs_en_cola"] = "OK"

        pag.goto(base + "#tickets")
        pag.wait_for_selector("text=Ana María Pérez Soto")
        pag.wait_for_selector("text=Luis Pérez Soto")
        pag.screenshot(path=CAPTURAS / "06-solicitudes.png", full_page=True)
        # Aprobar el #13 (10 nov): todavía no toca lanzarlo → solo etiqueta
        fila = pag.locator(".ticket", has_text="Luis Pérez Soto")
        antes = len(gh.despachos)
        fila.locator("text=Aprobar").click()
        pag.wait_for_selector("text=Aprobada. Su corrida se lanza sola")
        assert "aprobada" in [x["name"] for x in gh.issues[13]["labels"]]
        assert len(gh.despachos) == antes, "un ticket del 10/11 no se lanza el 05/11"
        # Quitar y borrar el #12 (cancela su corrida en curso)
        pag.once("dialog", lambda d: d.accept())
        pag.locator(".ticket", has_text="Ana María Pérez Soto").locator("text=Quitar y borrar datos").click()
        pag.wait_for_selector("text=Quitada y datos borrados")
        assert gh.issues[12]["state"] == "closed" and "upbv1" not in gh.issues[12]["body"]
        assert ("POST", f"/repos/{REPO}/actions/runs/501/cancel") in gh.llamadas
        resultados["acciones_admin"] = "OK"

        # Pegar de WhatsApp: texto con ruido (hora, nombre, línea de título) → se crea PENDIENTE, con salas en el título
        tok = sol.cifrar({"v": 1, "nombre": "Rosa", "apellido": "Quispe", "codigo": "44444", "proposito": "Estudio", "horario": "12:15-14:15",
                          "salas": ["15", "3"], "fecha": "2026-11-13", "ntfy": ""}, PUB)
        antes = set(gh.issues)
        pag.fill("#wsp-texto", f"[10:32, 12/11/2026] Rosa: Solicitudes de sala (cifradas):\nUPB|2026-11-13|12:15-14:15|R0S4QP|{tok}|B,C\n")
        pag.click("text=Crear solicitud(es)")
        pag.wait_for_selector("text=1 solicitud(es) creada(s) como pendientes")
        nuevo = gh.issues[max(set(gh.issues) - antes)]
        assert "salas B,C" in nuevo["title"] and "ref R0S4QP" in nuevo["title"] and nuevo["labels"] == [], nuevo
        assert sol.descifrar(nuevo["body"], CLAVE)["codigo"] == "44444"
        pag.fill("#wsp-texto", "hola, quiero sala")
        pag.click("text=Crear solicitud(es)")
        pag.wait_for_selector("text=No encontré ninguna solicitud")
        resultados["pegar_whatsapp"] = "OK"

        pag.goto(base + "#ajustes")
        pag.wait_for_selector("#a-nombre")
        pag.screenshot(path=CAPTURAS / "07-ajustes.png", full_page=True)
        pag.fill("#a-motivo", "Proyecto de software")
        pag.click("text=10:00 – 12:00")
        pag.check("#a-pausa")
        pag.click("text=Guardar cambios")
        pag.wait_for_selector("text=Cambios guardados")
        v = gh.variables
        assert v["UPB_HORARIO"] == "10:00-12:00" and v["UPB_PROPOSITO"] == "Proyecto de software" and v["UPB_PAUSADO"] == "1", v
        assert v["UPB_SALAS"] == "8,6,15,3", v
        pub = json.loads(gh.contenido["servicio.json"])  # el bloqueo público sigue a tus ajustes
        assert pub["bloqueo"] == {"sala": "8", "horario": "10:00-12:00"} and pub["plazo"] == "18:30", pub
        assert "Hugo" not in gh.contenido["servicio.json"] and "95503" not in gh.contenido["servicio.json"]
        resultados["ajustes"] = "OK"

        pag.goto(base + "#guia")
        pag.wait_for_selector("text=Revisar permisos")
        pag.click("text=Revisar permisos")
        pag.wait_for_selector("text=Puede leer")
        pag.once("dialog", lambda d: d.accept())
        pag.click("text=Crear una llave nueva")
        pag.wait_for_selector("text=Llave creada", timeout=20000)
        nueva_priv = pag.evaluate("localStorage.getItem('upb_privada')")
        assert gh.contenido.get("clave_publica.txt") and nueva_priv != PRIV
        tok = sol.cifrar({"x": 1}, gh.contenido["clave_publica.txt"])
        assert sol.descifrar(tok, sol.cargar_clave_privada(nueva_priv)) == {"x": 1}  # la llave creada en el teléfono sirve al bot
        resultados["llave_desde_telefono"] = "OK"
        pag.screenshot(path=CAPTURAS / "08-guia.png", full_page=True)

        # Viernes 19:20: el plazo del sábado venció; el siguiente día reservable es el lunes (domingo no).
        pv = nav.new_context(viewport={"width": 390, "height": 844}, locale="es-BO", color_scheme="dark")
        pv.route("**/*", enrutar)
        pvp = pv.new_page()
        pvp.on("pageerror", lambda e: errores.append(f"pageerror(viernes): {e}"))
        pvp.clock.set_fixed_time("2026-11-06T19:20:00-04:00")
        pvp.goto(base + "#pedir")
        pvp.wait_for_selector("text=Ya pasó el plazo para el sáb. 7 de noviembre")
        pvp.wait_for_selector("text=Para el lun. 9 de noviembre tienes hasta el dom. 8 de noviembre a las 18:30")
        assert pvp.locator("text=Para el dom. 8").count() == 0, "nunca debe ofrecer un domingo"
        caja_barra = pvp.locator("#usuario-barra").bounding_box()
        assert caja_barra["x"] + caja_barra["width"] <= 390 + 0.5, f"la barra se sale de la pantalla: {caja_barra}"
        pvp.screenshot(path=CAPTURAS / "11-viernes-celular-oscuro.png")
        resultados["plazos_saltan_domingo_y_barra_cabe"] = "OK"

        # Copia publicada en otro dominio: no funciona
        pc = nav.new_context(viewport={"width": 390, "height": 844}, locale="es-BO")
        pc.route("**/*", enrutar)
        pcp = pc.new_page()
        pcp.on("pageerror", lambda e: errores.append(f"pageerror(copia): {e}"))
        pcp.goto("http://copia.example/#pedir")
        pcp.wait_for_selector("text=Esta es una copia no autorizada")
        assert pcp.query_selector("#t-nombre") is None
        pcp.screenshot(path=CAPTURAS / "10-copia-no-autorizada.png")
        resultados["copia_no_autorizada"] = "OK"

        # Escritorio
        esc = nav.new_context(viewport={"width": 1280, "height": 800}, locale="es-BO")
        esc.route("**/*", enrutar)
        pe = esc.new_page()
        pe.clock.set_fixed_time("2026-11-05T19:20:00-04:00")
        pe.on("pageerror", lambda e: errores.append(f"pageerror(escritorio): {e}"))
        pe.goto(base + "#pedir")
        pe.wait_for_selector("#t-nombre")
        pe.screenshot(path=CAPTURAS / "09-escritorio-pedir.png", full_page=True)
        nav.close()
    srv.shutdown()
    print(json.dumps(resultados, ensure_ascii=False, indent=1))
    if errores:
        print("ERRORES JS:", *errores, sep="\n  ")
        sys.exit(1)
    print("Sin errores de JavaScript. Capturas en", CAPTURAS)


if __name__ == "__main__":
    main()
