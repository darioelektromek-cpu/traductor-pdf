"""
Servidor del traductor de PDF.

Local:     python app.py
Hosting:   Passenger lo carga mediante passenger_wsgi.py
"""

from __future__ import annotations

import argparse
import base64
import hmac
import json
import logging
import os
import re
import shutil
import socket
import tempfile
import threading
import time
import uuid
import webbrowser
from pathlib import Path

import pymupdf
from flask import Flask, Response, abort, jsonify, render_template, request, send_file

from traductor import (
    IDIOMAS,
    MOTORES,
    ErrorTraduccion,
    crear_traductor,
    elegir_fuente,
    extraer_bloques,
    traducir_pagina,
)

BASE_DIR = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Configuración (variables de entorno para el hosting)
# --------------------------------------------------------------------------

MAX_MB = int(os.environ.get("TRADUCTOR_MAX_MB", "200") or 200)
USUARIO = os.environ.get("TRADUCTOR_USUARIO", "").strip()
CLAVE = os.environ.get("TRADUCTOR_CLAVE", "").strip()
EDAD_MAXIMA = 24 * 60 * 60  # trabajos temporales: 24 h
ESPERA_MAXIMA = 15 * 60  # un trabajo sin avances durante 15 min se da por perdido


def _directorio_datos() -> Path:
    elegido = os.environ.get("TRADUCTOR_DATOS", "").strip()
    candidatos = [Path(elegido)] if elegido else []
    candidatos.append(BASE_DIR / "datos")
    candidatos.append(Path(tempfile.gettempdir()) / "traductor_pdf")

    for carpeta in candidatos:
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            prueba = carpeta / ".escritura"
            prueba.write_text("ok", encoding="utf-8")
            prueba.unlink(missing_ok=True)
            return carpeta
        except OSError:
            continue
    return Path(tempfile.gettempdir())


DATOS_DIR = _directorio_datos()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("traductor")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024
app.json.ensure_ascii = False

# Solo en memoria: las claves API nunca se escriben en disco.
SECRETOS: dict[str, dict] = {}
CANDADO = threading.Lock()
_RE_ID = re.compile(r"^[a-f0-9]{12}$")


# --------------------------------------------------------------------------
# Utilidades de archivos
# --------------------------------------------------------------------------


def _limpiar_nombre(nombre: str) -> str:
    nombre = Path(nombre).name
    nombre = re.sub(r"[^A-Za-z0-9._()\- ]+", "_", nombre).strip(" .")
    return nombre or "documento.pdf"


def _carpeta(job_id: str) -> Path:
    if not _RE_ID.match(job_id):
        abort(404)
    return DATOS_DIR / job_id


def _ruta_estado(job_id: str) -> Path:
    return _carpeta(job_id) / "estado.json"


def _leer_estado(job_id: str) -> dict | None:
    ruta = _ruta_estado(job_id)
    try:
        with ruta.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _escribir_estado(estado: dict) -> None:
    ruta = _ruta_estado(estado["id"])
    temporal = ruta.with_suffix(".tmp")
    with temporal.open("w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False)
    os.replace(temporal, ruta)


def _actualizar(registro: dict, **campos) -> None:
    registro.update(campos)
    _escribir_estado(registro)


def _antiguedad(job_id: str) -> float:
    try:
        return time.time() - _ruta_estado(job_id).stat().st_mtime
    except OSError:
        return 0.0


def _limpiar_antiguos() -> None:
    """Borra trabajos de más de 24 h como máximo una vez por hora."""
    marca = DATOS_DIR / ".limpieza"
    try:
        if marca.exists() and time.time() - marca.stat().st_mtime < 3600:
            return
        marca.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass

    ahora = time.time()
    for carpeta in DATOS_DIR.iterdir():
        try:
            if carpeta.is_dir() and ahora - carpeta.stat().st_mtime > EDAD_MAXIMA:
                shutil.rmtree(carpeta, ignore_errors=True)
        except OSError:
            continue


def _mensaje_error(exc: Exception) -> str:
    if isinstance(exc, ErrorTraduccion):
        return str(exc)
    tipos_pdf = tuple(
        tipo
        for tipo in (
            getattr(pymupdf, "FileDataError", None),
            getattr(pymupdf, "EmptyFileError", None),
        )
        if isinstance(tipo, type)
    )
    if tipos_pdf and isinstance(exc, tipos_pdf):
        return "El archivo PDF está dañado o no se puede abrir."
    return (
        "No se pudo procesar el PDF. Comprueba que no esté dañado ni protegido. "
        f"Detalle: {exc.__class__.__name__}: {exc}"
    )


# --------------------------------------------------------------------------
# Procesamiento en segundo plano
# --------------------------------------------------------------------------


def ejecutar_trabajo(job_id: str) -> None:
    estado = _leer_estado(job_id)
    if estado is None:
        return

    with CANDADO:
        secretos = SECRETOS.pop(job_id, {})

    carpeta = _carpeta(job_id)
    ruta_entrada = carpeta / "entrada.pdf"
    destino: str = estado["destino"]
    origen: str = estado["origen"]

    doc = None
    try:
        doc = pymupdf.open(str(ruta_entrada))
        if doc.needs_pass and not doc.authenticate(""):
            raise ErrorTraduccion(
                "El PDF está protegido con contraseña. Quita la protección y vuelve a intentarlo."
            )
        if doc.page_count == 0:
            raise ErrorTraduccion("El PDF no contiene páginas.")

        total = doc.page_count
        _actualizar(estado, estado="procesando", total=total, mensaje="Analizando el documento…")

        muestra = []
        for i in range(min(total, 5)):
            muestra.append(doc[i].get_text())
        texto_muestra = " ".join(muestra)[:40000]

        traductor, detectado = crear_traductor(
            motor=estado["motor_solicitado"],
            origen=origen,
            destino=destino,
            texto_muestra=texto_muestra,
            deepl_key=secretos.get("deepl_key", ""),
            libre_url=secretos.get("libre_url", ""),
            libre_key=secretos.get("libre_key", ""),
        )

        fuente = elegir_fuente(destino)
        paginas_txt: list[str] = []
        sin_texto = 0
        bloques_totales = 0

        for numero in range(total):
            if (carpeta / "cancelar").exists():
                raise ErrorTraduccion("Trabajo cancelado por el usuario.")

            page = doc[numero]
            bloques = extraer_bloques(page)
            _actualizar(
                estado,
                pagina=numero + 1,
                motor=getattr(traductor, "nombre_activo", traductor.nombre),
                idioma_detectado=(
                    IDIOMAS.get(detectado, detectado) if detectado else None
                ),
                mensaje=f"Traduciendo la página {numero + 1} de {total}…",
            )

            if not bloques:
                sin_texto += 1
                paginas_txt.append(
                    f"--- Página {numero + 1}: sin texto seleccionable (posible escaneo) ---"
                )
                continue

            textos_pagina, _ = traducir_pagina(page, traductor, fuente, bloques)
            bloques_totales += len(bloques)

            detectado_actual = getattr(traductor, "idioma_detectado", None) or detectado
            _actualizar(
                estado,
                bloques=bloques_totales,
                idioma_detectado=(
                    IDIOMAS.get(detectado_actual, detectado_actual)
                    if detectado_actual
                    else None
                ),
            )

            paginas_txt.append(f"--- Página {numero + 1} ---\n{textos_pagina}")

        if (carpeta / "cancelar").exists():
            raise ErrorTraduccion("Trabajo cancelado por el usuario.")

        _actualizar(estado, mensaje="Guardando el PDF traducido…")
        nombre_base = re.sub(
            r"[^A-Za-z0-9._()\- ]+", "_", Path(estado["nombre_original"]).stem
        ).strip() or "documento"
        sufijo = destino.replace("-", "_")

        ruta_pdf = carpeta / f"{nombre_base}_{sufijo}.pdf"
        doc.save(str(ruta_pdf), garbage=3, deflate=True)
        doc.close()
        doc = None

        ruta_txt = carpeta / f"{nombre_base}_{sufijo}.txt"
        ruta_txt.write_text("\n\n".join(paginas_txt), encoding="utf-8")

        aviso = ""
        if sin_texto:
            if sin_texto == 1:
                aviso = (
                    "1 página no tiene texto seleccionable (probablemente es una "
                    "imagen escaneada) y se ha dejado sin cambios. Para esa página "
                    "haría falta OCR."
                )
            else:
                aviso = (
                    f"{sin_texto} de {total} páginas no tienen texto seleccionable "
                    "(probablemente son imágenes escaneadas) y se han dejado sin "
                    "cambios. Para esas páginas haría falta OCR."
                )

        _actualizar(
            estado,
            estado="listo",
            mensaje="Traducción completada.",
            aviso=aviso,
            nombre_pdf=ruta_pdf.name,
            nombre_txt=ruta_txt.name,
            bloques=bloques_totales,
            paginas_sin_texto=sin_texto,
            fin=time.time(),
        )
        log.info("Trabajo %s completado (%s páginas).", job_id, total)

    except Exception as exc:  # noqa: BLE001 - se informa al usuario
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        cancelado = "cancelado" in str(exc).lower()
        _actualizar(
            estado,
            estado="cancelado" if cancelado else "error",
            mensaje=str(exc) if cancelado else _mensaje_error(exc),
            error=None if cancelado else _mensaje_error(exc),
            fin=time.time(),
        )
        log.warning("Trabajo %s: %s", job_id, exc)


# --------------------------------------------------------------------------
# Autenticación opcional
# --------------------------------------------------------------------------


@app.before_request
def _proteger():
    if not (USUARIO and CLAVE):
        return None

    cabecera = request.headers.get("Authorization", "")
    if cabecera.startswith("Basic "):
        try:
            descifrado = base64.b64decode(cabecera[6:]).decode("utf-8")
            usuario, _, clave = descifrado.partition(":")
        except (ValueError, UnicodeDecodeError):
            usuario, clave = "", ""
        if hmac.compare_digest(usuario, USUARIO) and hmac.compare_digest(clave, CLAVE):
            return None

    return Response(
        "Acceso restringido. Introduce el usuario y la contraseña.",
        401,
        {"WWW-Authenticate": 'Basic realm="Traductor de PDF", charset="UTF-8"'},
    )


# --------------------------------------------------------------------------
# Rutas web
# --------------------------------------------------------------------------


@app.get("/")
def inicio():
    return render_template("index.html", idiomas=IDIOMAS, motores=MOTORES, max_mb=MAX_MB)


@app.post("/api/traducir")
def api_traducir():
    archivo = request.files.get("archivo")
    if archivo is None or not archivo.filename:
        return jsonify(error="Selecciona un archivo PDF."), 400

    nombre = _limpiar_nombre(archivo.filename)
    if not nombre.lower().endswith(".pdf"):
        return jsonify(error="El archivo debe tener extensión .pdf."), 400

    destino = (request.form.get("destino") or "es").strip()
    if destino not in IDIOMAS or destino == "auto":
        return jsonify(error="Elige un idioma de destino válido."), 400

    origen = (request.form.get("origen") or "auto").strip()
    if origen not in IDIOMAS:
        origen = "auto"

    motor = (request.form.get("motor") or "auto").strip()
    if motor not in MOTORES:
        motor = "auto"

    _limpiar_antiguos()
    job_id = uuid.uuid4().hex[:12]
    carpeta = DATOS_DIR / job_id
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_entrada = carpeta / "entrada.pdf"
    archivo.save(ruta_entrada)

    with open(ruta_entrada, "rb") as fh:
        cabecera = fh.read(5)
    if cabecera != b"%PDF-":
        shutil.rmtree(carpeta, ignore_errors=True)
        return jsonify(error="El archivo no parece un PDF válido."), 400

    estado = {
        "id": job_id,
        "estado": "en_cola",
        "mensaje": "Preparando el documento…",
        "pagina": 0,
        "total": 0,
        "bloques": 0,
        "motor": MOTORES.get(motor, motor),
        "idioma_detectado": None,
        "aviso": "",
        "error": None,
        "nombre_original": nombre,
        "destino": destino,
        "origen": origen,
        "motor_solicitado": motor,
        "cancelar": False,
        "inicio": time.time(),
    }
    _escribir_estado(estado)

    with CANDADO:
        SECRETOS[job_id] = {
            "deepl_key": (request.form.get("deepl_key") or "").strip(),
            "libre_url": (request.form.get("libre_url") or "").strip(),
            "libre_key": (request.form.get("libre_key") or "").strip(),
        }

    hilo = threading.Thread(target=ejecutar_trabajo, args=(job_id,), daemon=True)
    hilo.start()
    return jsonify(id=job_id)


@app.get("/api/progreso/<job_id>")
def api_progreso(job_id: str):
    estado = _leer_estado(job_id)
    if estado is None:
        return jsonify(error="Trabajo no encontrado."), 404

    if (
        estado["estado"] in ("en_cola", "procesando")
        and _antiguedad(job_id) > ESPERA_MAXIMA
    ):
        _actualizar(
            estado,
            estado="error",
            error=(
                "El trabajo se interrumpió (el servidor reinició el proceso o tardó "
                "demasiado). Vuelve a intentarlo, preferiblemente con un PDF más pequeño."
            ),
            mensaje=(
                "El trabajo se interrumpió (el servidor reinició el proceso o tardó "
                "demasiado). Vuelve a intentarlo, preferiblemente con un PDF más pequeño."
            ),
        )

    if estado["estado"] in ("en_cola", "procesando") and (
        _carpeta(job_id) / "cancelar"
    ).exists():
        estado["mensaje"] = "Cancelando…"

    datos = {
        clave: estado.get(clave)
        for clave in (
            "id",
            "estado",
            "mensaje",
            "pagina",
            "total",
            "bloques",
            "motor",
            "idioma_detectado",
            "aviso",
            "error",
            "nombre_pdf",
            "paginas_sin_texto",
        )
    }
    return jsonify(datos)


@app.post("/api/cancelar/<job_id>")
def api_cancelar(job_id: str):
    estado = _leer_estado(job_id)
    if estado is None:
        return jsonify(error="Trabajo no encontrado."), 404
    if estado["estado"] in ("listo", "error", "cancelado"):
        return jsonify(ok=True, mensaje="El trabajo ya había terminado.")
    try:
        (_carpeta(job_id) / "cancelar").write_text("1", encoding="utf-8")
    except OSError:
        return jsonify(error="No se pudo cancelar el trabajo."), 500
    return jsonify(ok=True)


@app.get("/api/descargar/<job_id>/<tipo>")
def api_descargar(job_id: str, tipo: str):
    estado = _leer_estado(job_id)
    if estado is None or estado["estado"] != "listo":
        abort(404)

    if tipo == "pdf":
        nombre = estado.get("nombre_pdf") or ""
    elif tipo == "txt":
        nombre = estado.get("nombre_txt") or ""
    else:
        abort(404)

    ruta = _carpeta(job_id) / nombre
    if not nombre or not ruta.is_file():
        abort(404)
    return send_file(ruta, as_attachment=True, download_name=nombre)


@app.get("/api/ver/<job_id>")
def api_ver(job_id: str):
    estado = _leer_estado(job_id)
    if estado is None or estado["estado"] != "listo":
        abort(404)
    nombre = estado.get("nombre_pdf") or ""
    ruta = _carpeta(job_id) / nombre
    if not nombre or not ruta.is_file():
        abort(404)
    respuesta = send_file(
        ruta,
        mimetype="application/pdf",
        download_name=nombre,
        as_attachment=False,
    )
    respuesta.headers["Content-Disposition"] = f'inline; filename="{nombre}"'
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@app.errorhandler(413)
def demasiado_grande(_error):
    return jsonify(error=f"El archivo supera el límite de {MAX_MB} MB."), 413


@app.get("/api/salud")
def salud():
    return jsonify(ok=True, version=pymupdf.__version__, almacen=str(DATOS_DIR))


# --------------------------------------------------------------------------
# Arranque local
# --------------------------------------------------------------------------


def _puerto_libre(inicial: int) -> int:
    for puerto in range(inicial, inicial + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:
                return puerto
    return inicial


def main() -> None:
    parser = argparse.ArgumentParser(description="Traductor de PDF local")
    parser.add_argument("--puerto", type=int, default=5000)
    parser.add_argument("--sin-navegador", action="store_true")
    args = parser.parse_args()

    _limpiar_antiguos()
    puerto = _puerto_libre(args.puerto)
    url = f"http://127.0.0.1:{puerto}"

    print()
    print("  Traductor de PDF")
    print(f"  Abre esta direccion en el navegador: {url}")
    print("  Para detenerlo, pulsa Ctrl+C.")
    print()

    if not args.sin_navegador:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    app.run(host="127.0.0.1", port=puerto, debug=False, threaded=True)


if __name__ == "__main__":
    main()
