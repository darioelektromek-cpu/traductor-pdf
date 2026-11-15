"""
Núcleo del traductor de PDF.

- Extrae el texto real del PDF respetando bloques y líneas.
- Traduce con varios motores (Google, MyMemory, DeepL, LibreTranslate).
- Reconstruye el PDF: borra el texto original y escribe la traducción
  en el mismo espacio, reduciendo el tamaño de fuente hasta que encaje.
"""

from __future__ import annotations

import html
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
import requests

# --------------------------------------------------------------------------
# Configuración general
# --------------------------------------------------------------------------

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 45

IDIOMAS: dict[str, str] = {
    "auto": "Detectar automáticamente",
    "en": "Inglés",
    "es": "Español",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
    "pt": "Portugués",
    "ru": "Ruso",
    "zh-CN": "Chino simplificado",
    "ja": "Japonés",
    "ko": "Coreano",
    "ar": "Árabe",
    "hi": "Hindi",
    "nl": "Neerlandés",
    "pl": "Polaco",
    "tr": "Turco",
    "sv": "Sueco",
    "uk": "Ucraniano",
    "ro": "Rumano",
    "el": "Griego",
    "cs": "Checo",
    "da": "Danés",
    "fi": "Finlandés",
    "no": "Noruego",
    "hu": "Húngaro",
    "id": "Indonesio",
    "vi": "Vietnamita",
    "th": "Tailandés",
    "he": "Hebreo",
    "fa": "Persa",
}

MOTORES: dict[str, str] = {
    "auto": "Automático (recomendado)",
    "google": "Google",
    "mymemory": "MyMemory",
    "deepl": "DeepL (clave API)",
    "libre": "LibreTranslate (servidor propio)",
}


class ErrorTraduccion(RuntimeError):
    """Fallo controlado que se muestra tal cual al usuario."""


# --------------------------------------------------------------------------
# Detección de idioma (solo se usa cuando el motor no admite "auto")
# --------------------------------------------------------------------------

_PALABRAS: dict[str, set[str]] = {
    "en": set(
        "the and of to in is that it for with as was on be this are from by or an "
        "not have at which but they you we his her their there can will would".split()
    ),
    "es": set(
        "el la de que y en a los se del las un por con no una para es al lo como "
        "más pero sus le ya o este sí porque esta entre cuando muy sin sobre también".split()
    ),
    "fr": set(
        "le la les de et des en un une du est que pour dans qui sur pas au avec ce "
        "sont mais ou plus par son il elle nous vous ils elles cette".split()
    ),
    "de": set(
        "der die und in den von zu das mit sich des auf für ist im nicht ein eine "
        "als auch es an dem werden aus er hat dass sie nach wird bei".split()
    ),
    "pt": set(
        "o a os as de que e do da em um uma para com não se na no por mais dos como "
        "mas foi ao ele ela são você isso".split()
    ),
    "it": set(
        "il la di e che a un in per è non una con si da le dei del al come più "
        "anche questo questa sono gli delle alla nel".split()
    ),
    "nl": set(
        "de het een en van in is dat op te voor met zijn niet aan er om ook als "
        "maar bij door uit dan nog".split()
    ),
    "ru": set(
        "и в не на что это с по как из к у за от но для же бы или так его она они "
        "мы вы быть был была".split()
    ),
    "tr": set(
        "ve bir bu da de için ile çok olarak daha gibi ne var olan ama veya en "
        "kadar sonra".split()
    ),
    "id": set(
        "dan yang di untuk dengan ini dari tidak pada akan juga ke dalam itu "
        "adalah atau karena".split()
    ),
    "sv": set(
        "och att det som en på är av för med till den inte har om ett jag vi "
        "de kan".split()
    ),
    "pl": set(
        "i w na z że do się nie jest o jak po co tak ale od za przez oraz "
        "jest są".split()
    ),
}

_RE_PALABRA = re.compile(r"[^\W\d_]+", re.UNICODE)


def detectar_idioma(texto: str) -> str | None:
    """Heurística sencilla por palabras frecuentes. Devuelve un código o None."""
    palabras = [p.lower() for p in _RE_PALABRA.findall(texto[:20000])]
    if len(palabras) < 12:
        return None
    total = len(palabras)
    puntuaciones = {
        codigo: sum(1 for p in palabras if p in vocabulario) / total
        for codigo, vocabulario in _PALABRAS.items()
    }
    codigo, puntos = max(puntuaciones.items(), key=lambda kv: kv[1])
    return codigo if puntos >= 0.03 else None


def _nombre_idioma(codigo: str | None) -> str:
    if not codigo:
        return "idioma desconocido"
    return IDIOMAS.get(codigo, codigo)


# --------------------------------------------------------------------------
# Utilidades de texto
# --------------------------------------------------------------------------


def trocear(texto: str, limite: int) -> list[str]:
    """Corta un texto largo por espacios sin superar el límite."""
    if len(texto) <= limite:
        return [texto]
    partes: list[str] = []
    resto = texto
    while len(resto) > limite:
        corte = resto.rfind(" ", 0, limite)
        if corte < limite * 0.4:
            corte = limite
        partes.append(resto[:corte])
        resto = resto[corte:].lstrip()
    if resto:
        partes.append(resto)
    return partes


def _limpiar(texto: str) -> str:
    texto = texto.replace("\u00ad", "").replace("\u200b", "")
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


def _tiene_letras(texto: str) -> bool:
    """Los números y símbolos sueltos no necesitan traducción."""
    return any(caracter.isalpha() for caracter in texto)


# --------------------------------------------------------------------------
# Motores de traducción
# --------------------------------------------------------------------------


class Traductor:
    nombre = "base"
    soporta_auto = False

    def disponible(self) -> bool:
        return True

    def traducir(self, texto: str) -> str:  # pragma: no cover - interfaz
        raise NotImplementedError

    def traducir_bloques(self, textos: list[str]) -> list[str]:
        salida: list[str] = []
        for texto in textos:
            if not texto.strip() or not _tiene_letras(texto):
                salida.append(texto)
            else:
                salida.append(self.traducir(texto))
        return salida


class TraductorGoogle(Traductor):
    nombre = "Google"
    soporta_auto = True
    URL = "https://translate.googleapis.com/translate_a/single"

    def __init__(self, origen: str, destino: str):
        self.origen = origen or "auto"
        self.destino = destino
        self.sesion = requests.Session()
        self.sesion.headers.update(UA)
        self.cache: dict[str, str] = {}
        self.idioma_detectado: str | None = None

    # -- petición individual ------------------------------------------------
    def _pedir(self, texto: str) -> str:
        if not texto.strip():
            return texto
        if texto in self.cache:
            return self.cache[texto]

        params = {
            "client": "gtx",
            "sl": self.origen,
            "tl": self.destino,
            "dt": "t",
        }
        ultimo_error = ""
        for intento in range(3):
            try:
                r = self.sesion.post(
                    self.URL, params=params, data={"q": texto}, timeout=TIMEOUT
                )
                if r.status_code == 429:
                    ultimo_error = (
                        "Google rechazó la petición por límite de uso (HTTP 429)."
                    )
                    time.sleep(1.2 * (intento + 1))
                    continue
                if r.status_code >= 400:
                    ultimo_error = f"Google respondió HTTP {r.status_code}."
                    time.sleep(0.8 * (intento + 1))
                    continue
                datos = r.json()
                if self.origen == "auto" and self.idioma_detectado is None:
                    try:
                        posible = datos[2]
                        if isinstance(posible, str) and posible:
                            self.idioma_detectado = posible
                    except (IndexError, TypeError):
                        pass
                segmentos = datos[0] or []
                traduccion = "".join(s[0] for s in segmentos if s and s[0])
                if texto.strip() and not traduccion.strip():
                    ultimo_error = "Google devolvió una traducción vacía."
                    continue
                traduccion = html.unescape(traduccion).strip()
                self.cache[texto] = traduccion
                return traduccion
            except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
                ultimo_error = f"No se pudo contactar con Google ({exc.__class__.__name__})."
                time.sleep(0.8 * (intento + 1))

        raise ErrorTraduccion(ultimo_error or "Error desconocido al llamar a Google.")

    def disponible(self) -> bool:
        try:
            self._pedir("hello")
            return True
        except ErrorTraduccion:
            return False

    # -- lotes con separadores ---------------------------------------------
    DELIM_RE = re.compile(r"\[\s*\[\s*\[\s*(\d+)\s*\]\s*\]\s*\]")

    def traducir_bloques(self, textos: list[str]) -> list[str]:
        resultados: list[str | None] = [None] * len(textos)
        pendientes: list[int] = []

        for i, texto in enumerate(textos):
            if not texto.strip() or not _tiene_letras(texto):
                resultados[i] = texto
            elif texto in self.cache:
                resultados[i] = self.cache[texto]
            else:
                pendientes.append(i)

        grupos: list[list[int]] = []
        actual: list[int] = []
        largo = 0
        for i in pendientes:
            tam = len(textos[i])
            if actual and (largo + tam > 2800 or len(actual) >= 20):
                grupos.append(actual)
                actual, largo = [], 0
            actual.append(i)
            largo += tam
        if actual:
            grupos.append(actual)

        for grupo in grupos:
            # Un bloque demasiado largo se trocea antes de enviarlo.
            if len(grupo) == 1 and len(textos[grupo[0]]) > 2800:
                i = grupo[0]
                partes = trocear(textos[i], 2800)
                resultados[i] = " ".join(self._pedir(p) for p in partes)
                continue

            unido = "".join(
                "\n[[[%d]]]\n%s" % (k, textos[i]) for k, i in enumerate(grupo)
            )
            respuesta = self._pedir(unido)
            trozos = self.DELIM_RE.split(respuesta)
            if trozos and trozos[0].strip() == "":
                numeros = [int(n) for n in trozos[1::2]]
                valores = trozos[2::2]
                if numeros == list(range(len(grupo))) and len(valores) == len(grupo):
                    for i, valor in zip(grupo, valores):
                        resultados[i] = _limpiar(html.unescape(valor))
                    continue
            # Si los separadores se perdieron, traducimos uno a uno.
            for i in grupo:
                resultados[i] = self._pedir(textos[i])

        return [r if r is not None else "" for r in resultados]


class TraductorMyMemory(Traductor):
    nombre = "MyMemory"
    soporta_auto = False
    URL = "https://api.mymemory.translated.net/get"
    LIMITE = 450

    def __init__(self, origen: str, destino: str):
        self.origen = origen
        self.destino = destino
        self.sesion = requests.Session()
        self.sesion.headers.update(UA)
        self.cache: dict[str, str] = {}

    def _pedir(self, texto: str) -> str:
        if not texto.strip():
            return texto
        if texto in self.cache:
            return self.cache[texto]

        params = {"q": texto, "langpair": f"{self.origen}|{self.destino}"}
        ultimo_error = ""
        for intento in range(3):
            try:
                r = self.sesion.get(self.URL, params=params, timeout=TIMEOUT)
                if r.status_code == 429:
                    ultimo_error = (
                        "MyMemory alcanzó el límite diario de traducciones gratuitas."
                    )
                    time.sleep(1.0 * (intento + 1))
                    continue
                if r.status_code >= 400:
                    ultimo_error = f"MyMemory respondió HTTP {r.status_code}."
                    time.sleep(0.8 * (intento + 1))
                    continue

                datos = r.json()
                estado = datos.get("responseStatus")
                if datos.get("quotaFinished"):
                    raise ErrorTraduccion(
                        "MyMemory agotó la cuota gratuita diaria de esta IP. "
                        "Prueba con otro motor o espera 24 h."
                    )
                if estado not in (200, "200"):
                    detalle = datos.get("responseDetails") or "respuesta no válida"
                    raise ErrorTraduccion(f"MyMemory: {detalle}")

                traduccion = (datos.get("responseData") or {}).get("translatedText") or ""
                traduccion = _limpiar(html.unescape(traduccion))
                if not traduccion and texto.strip():
                    raise ErrorTraduccion("MyMemory devolvió una traducción vacía.")
                self.cache[texto] = traduccion
                return traduccion
            except (requests.RequestException, ValueError) as exc:
                ultimo_error = (
                    f"No se pudo contactar con MyMemory ({exc.__class__.__name__})."
                )
                time.sleep(0.8 * (intento + 1))

        raise ErrorTraduccion(ultimo_error or "Error desconocido al llamar a MyMemory.")

    def traducir(self, texto: str) -> str:
        if not _tiene_letras(texto):
            return texto
        if len(texto) <= self.LIMITE:
            return self._pedir(texto)
        partes = trocear(texto, self.LIMITE)
        return " ".join(self._pedir(p) for p in partes)


class TraductorDeepL(Traductor):
    nombre = "DeepL"
    soporta_auto = True

    CODIGOS = {
        "en": "EN",
        "es": "ES",
        "fr": "FR",
        "de": "DE",
        "it": "IT",
        "pt": "PT-PT",
        "ru": "RU",
        "ja": "JA",
        "zh-CN": "ZH",
        "ko": "KO",
        "nl": "NL",
        "pl": "PL",
        "tr": "TR",
        "sv": "SV",
        "da": "DA",
        "fi": "FI",
        "cs": "CS",
        "el": "EL",
        "hu": "HU",
        "ro": "RO",
        "uk": "UK",
        "id": "ID",
        "ar": "AR",
    }

    def __init__(self, origen: str, destino: str, clave: str):
        self.origen = (origen or "").lower()
        self.destino = destino
        self.clave = clave.strip()
        self.sesion = requests.Session()
        self.sesion.headers.update(UA)

    def disponible(self) -> bool:
        return bool(self.clave)

    def traducir_bloques(self, textos: list[str]) -> list[str]:
        resultados: list[str | None] = [None] * len(textos)
        indices = [
            i for i, t in enumerate(textos) if t.strip() and _tiene_letras(t)
        ]
        for i, t in enumerate(textos):
            if not t.strip() or not _tiene_letras(t):
                resultados[i] = t

        # DeepL admite hasta 50 textos y 128 KiB por petición.
        for inicio in range(0, len(indices), 50):
            lote = indices[inicio : inicio + 50]
            datos = [("text", textos[i]) for i in lote]
            datos += [("target_lang", self.CODIGOS.get(self.destino, self.destino.upper()))]
            if self.origen and self.origen != "auto":
                datos.append(
                    ("source_lang", self.CODIGOS.get(self.origen, self.origen.upper()))
                )

            url = (
                "https://api-free.deepl.com/v2/translate"
                if self.clave.endswith(":fx")
                else "https://api.deepl.com/v2/translate"
            )
            try:
                r = self.sesion.post(
                    url,
                    headers={"Authorization": f"DeepL-Auth-Key {self.clave}"},
                    data=datos,
                    timeout=TIMEOUT,
                )
            except requests.RequestException as exc:
                raise ErrorTraduccion(
                    f"No se pudo contactar con DeepL ({exc.__class__.__name__})."
                ) from exc

            if r.status_code == 403:
                raise ErrorTraduccion("DeepL rechazó la clave API (HTTP 403).")
            if r.status_code == 456:
                raise ErrorTraduccion("La cuota de DeepL se ha agotado (HTTP 456).")
            if r.status_code >= 400:
                raise ErrorTraduccion(f"DeepL respondió HTTP {r.status_code}.")

            traducciones = [t.get("text", "") for t in r.json().get("translations", [])]
            if len(traducciones) != len(lote):
                raise ErrorTraduccion("DeepL devolvió un número de textos inesperado.")
            for i, traduccion in zip(lote, traducciones):
                resultados[i] = traduccion

        return [r or "" for r in resultados]


class TraductorLibre(Traductor):
    nombre = "LibreTranslate"
    soporta_auto = True

    def __init__(self, origen: str, destino: str, url: str, clave: str = ""):
        self.origen = origen or "auto"
        self.destino = destino
        self.url = url.rstrip("/")
        if not self.url.endswith("/translate"):
            self.url += "/translate"
        self.clave = clave.strip()
        self.sesion = requests.Session()
        self.sesion.headers.update(UA)

    def disponible(self) -> bool:
        return bool(self.url)

    def traducir(self, texto: str) -> str:
        if not texto.strip() or not _tiene_letras(texto):
            return texto
        cuerpo = {
            "q": texto,
            "source": self.origen,
            "target": self.destino,
            "format": "text",
        }
        if self.clave:
            cuerpo["api_key"] = self.clave
        try:
            r = self.sesion.post(self.url, json=cuerpo, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise ErrorTraduccion(
                f"No se pudo contactar con LibreTranslate ({exc.__class__.__name__})."
            ) from exc
        if r.status_code >= 400:
            detalle = ""
            try:
                detalle = r.json().get("error", "")
            except ValueError:
                pass
            raise ErrorTraduccion(
                f"LibreTranslate respondió HTTP {r.status_code}. {detalle}".strip()
            )
        return (r.json().get("translatedText") or "").strip()


class TraductorAuto(Traductor):
    """Prueba motores en orden y cambia al siguiente si uno falla."""

    nombre = "Automático"

    def __init__(self, opciones: list[Traductor]):
        self._opciones = opciones
        self.activo: Traductor | None = None

    @property
    def nombre_activo(self) -> str:
        return self.activo.nombre if self.activo else self.nombre

    @property
    def idioma_detectado(self) -> str | None:
        return getattr(self.activo, "idioma_detectado", None) if self.activo else None

    def _elegir(self) -> Traductor:
        while self._opciones:
            candidato = self._opciones.pop(0)
            if candidato.disponible():
                self.activo = candidato
                return candidato
        raise ErrorTraduccion(
            "Ningún motor de traducción está disponible. Revisa tu conexión a "
            "internet o configura DeepL/LibreTranslate."
        )

    def traducir_bloques(self, textos: list[str]) -> list[str]:
        if self.activo is None:
            self._elegir()
        while True:
            try:
                return self.activo.traducir_bloques(textos)  # type: ignore[union-attr]
            except ErrorTraduccion:
                if not self._opciones:
                    raise
                self.activo = None
                self._elegir()


def crear_traductor(
    motor: str,
    origen: str,
    destino: str,
    texto_muestra: str = "",
    deepl_key: str = "",
    libre_url: str = "",
    libre_key: str = "",
) -> tuple[Traductor, str | None]:
    """Devuelve el traductor listo para usar y el idioma detectado (si hubo)."""
    detectado: str | None = None
    origen_real = origen or "auto"

    if origen_real == "auto" and motor != "google":
        detectado = detectar_idioma(texto_muestra)
        if detectado is None and motor in ("mymemory", "auto"):
            detectado = "en"

    if motor == "google":
        return TraductorGoogle(origen_real, destino), detectado

    if motor == "mymemory":
        return TraductorMyMemory(detectado or "en", destino), detectado

    if motor == "deepl":
        if not deepl_key.strip():
            raise ErrorTraduccion("Falta la clave API de DeepL.")
        return TraductorDeepL(origen_real, destino, deepl_key), detectado

    if motor == "libre":
        if not libre_url.strip():
            raise ErrorTraduccion("Falta la URL del servidor LibreTranslate.")
        return TraductorLibre(origen_real, destino, libre_url, libre_key), detectado

    # Automático
    opciones: list[Traductor] = [TraductorGoogle(origen_real, destino)]
    opciones.append(TraductorMyMemory(detectado or "en", destino))
    if deepl_key.strip():
        opciones.append(TraductorDeepL(origen_real, destino, deepl_key))
    if libre_url.strip():
        opciones.append(TraductorLibre(origen_real, destino, libre_url, libre_key))
    return TraductorAuto(opciones), detectado


# --------------------------------------------------------------------------
# Extracción y reconstrucción del PDF
# --------------------------------------------------------------------------


@dataclass
class Linea:
    rect: pymupdf.Rect
    texto: str
    tamano: float
    color: tuple[float, float, float]
    alineacion: int


@dataclass
class Bloque:
    rect: pymupdf.Rect
    texto: str
    tamano: float
    color: tuple[float, float, float]
    alineacion: int  # 0 izquierda, 1 centro, 2 derecha
    lineas: list[Linea] = field(default_factory=list)
    tabular: bool = False


def _es_tabular(rect: pymupdf.Rect, lineas: list[Linea], tamano: float) -> bool:
    """Detecta tablas, índices y bloques de líneas cortas y muy juntas."""
    if not (3 <= len(lineas) <= 200):
        return False
    if rect.width < 110:
        return False
    mediana = statistics.median(len(l.texto) for l in lineas)
    alto_medio = rect.height / len(lineas)
    return mediana <= 26 and alto_medio <= max(15.0, tamano * 1.9)


def _alineacion_linea(rect: pymupdf.Rect, padre: pymupdf.Rect) -> int:
    if padre.width <= 0 or rect.width >= padre.width - 2:
        return 0
    if abs(rect.x1 - padre.x1) <= 2:
        return 2
    centro = (rect.x0 + rect.x1) / 2
    centro_padre = (padre.x0 + padre.x1) / 2
    if abs(centro - centro_padre) <= 2.5:
        return 1
    return 0


def _color_rgb(valor: int) -> tuple[float, float, float]:
    return (
        ((valor >> 16) & 255) / 255.0,
        ((valor >> 8) & 255) / 255.0,
        (valor & 255) / 255.0,
    )


def _unir_lineas(lineas: list[str]) -> str:
    """Une líneas respetando guiones de corte y párrafos."""
    resultado = ""
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        if not resultado:
            resultado = linea
        elif resultado.endswith("-") and linea[:1].islower():
            resultado = resultado[:-1] + linea
        else:
            resultado += "\n" + linea
    return resultado


def extraer_bloques(page: pymupdf.Page) -> list[Bloque]:
    bloques: list[Bloque] = []
    datos = page.get_text("dict")

    for bruto in datos.get("blocks", []):
        if bruto.get("type") != 0:
            continue

        lineas: list[Linea] = []
        tamanos: list[tuple[int, float]] = []
        colores: dict[int, int] = {}

        for linea in bruto.get("lines", []):
            spans = linea.get("spans", [])
            texto_linea = "".join(s.get("text", "") for s in spans)
            if not texto_linea.strip():
                continue

            tam_linea = 10.0
            peso_color: dict[int, int] = {}
            mejor_peso = -1
            for span in spans:
                contenido = span.get("text", "")
                if not contenido.strip():
                    continue
                peso = len(contenido)
                tam = float(span.get("size", 10))
                if peso > mejor_peso:
                    mejor_peso = peso
                    tam_linea = tam
                color_span = int(span.get("color", 0))
                peso_color[color_span] = peso_color.get(color_span, 0) + peso
                tamanos.append((peso, tam))
                colores[color_span] = colores.get(color_span, 0) + peso

            color_linea = (
                max(peso_color.items(), key=lambda kv: kv[1])[0] if peso_color else 0
            )
            lineas.append(
                Linea(
                    rect=pymupdf.Rect(linea["bbox"]),
                    texto=texto_linea,
                    tamano=max(4.0, min(tam_linea, 96.0)),
                    color=_color_rgb(color_linea),
                    alineacion=0,
                )
            )

        if not lineas:
            continue

        texto = _unir_lineas([l.texto for l in lineas])
        if not texto.strip():
            continue

        rect_bloque = pymupdf.Rect(bruto["bbox"])
        tamano = max(tamanos, key=lambda t: t[0])[1] if tamanos else 10.0
        color = max(colores.items(), key=lambda kv: kv[1])[0] if colores else 0

        # Alineación aproximada del bloque a partir de sus líneas.
        alineacion = 0
        if rect_bloque.width > 20:
            margen_izq = statistics.median(l.rect.x0 - rect_bloque.x0 for l in lineas)
            margen_der = statistics.median(rect_bloque.x1 - l.rect.x1 for l in lineas)
            centro_bloque = (rect_bloque.x0 + rect_bloque.x1) / 2
            centrado = all(
                abs((l.rect.x0 + l.rect.x1) / 2 - centro_bloque) < 3 for l in lineas
            )
            if centrado and margen_izq > 6 and margen_der > 6:
                alineacion = 1
            elif margen_izq > 25 and margen_der < 8:
                alineacion = 2

        bloque = Bloque(
            rect=rect_bloque,
            texto=texto,
            tamano=max(4.0, min(tamano, 96.0)),
            color=_color_rgb(color),
            alineacion=alineacion,
            lineas=lineas,
        )
        bloque.tabular = _es_tabular(rect_bloque, lineas, bloque.tamano)
        for linea in lineas:
            linea.alineacion = _alineacion_linea(linea.rect, rect_bloque)

        bloques.append(bloque)

    bloques.sort(key=lambda b: (round(b.rect.y0, 1), b.rect.x0))
    return bloques


# --- fuentes --------------------------------------------------------------

_FUENTES_SISTEMA = {
    "cjk": [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/meiryo.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ],
    "normal": [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
}


BASE_DIR = Path(__file__).resolve().parent
FUENTES_DIR = BASE_DIR / "fuentes"

# Extensiones de fuente que PyMuPDF puede incrustar.
_EXTENSIONES_FUENTE = (".ttf", ".otf", ".ttc")


def _fuente_local(grupo: str) -> Path | None:
    """Busca fuentes dentro de la carpeta `fuentes/` del proyecto.

    En el hosting no existen las fuentes de Windows, así que el usuario
    puede copiar ahí sus propios archivos. Se prioriza `cjk` para los
    idiomas chino, japonés y coreano.
    """
    if not FUENTES_DIR.is_dir():
        return None

    nombres_cjk = ("cjk", "noto", "cjkjp", "cjkko", "han", "song", "hei", "ming")
    nombres_normal = ("dejavu", "liberation", "arial", "segoe", "roboto", "open", "noto")

    archivos = sorted(
        p
        for p in FUENTES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in _EXTENSIONES_FUENTE
    )
    if not archivos:
        return None

    claves = nombres_cjk if grupo == "cjk" else nombres_normal
    for clave in claves:
        for archivo in archivos:
            if clave in archivo.name.lower():
                return archivo

    if grupo == "cjk":
        # Sin una fuente CJK reconocible es mejor no usar una latina a ciegas.
        return None
    return archivos[0]


def elegir_fuente(destino: str) -> Path | None:
    grupo = "cjk" if destino in {"zh-CN", "ja", "ko"} else "normal"

    local = _fuente_local(grupo)
    if local is not None:
        return local

    for ruta in _FUENTES_SISTEMA[grupo]:
        p = Path(ruta)
        if p.is_file():
            return p
    # Último recurso: cualquier TTF del sistema.
    for ruta in _FUENTES_SISTEMA["normal"]:
        p = Path(ruta)
        if p.is_file():
            return p
    return None


def _registrar_fuente(page: pymupdf.Page, fuente: Path | None) -> str | None:
    if fuente is None:
        return None
    try:
        page.insert_font(fontname="TRADPDF", fontfile=str(fuente))
        return "TRADPDF"
    except Exception:
        return None


def _insertar_texto(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    texto: str,
    tamano: float,
    color: tuple[float, float, float],
    alineacion: int,
    nombre_fuente: str | None,
) -> float:
    rect = pymupdf.Rect(rect)
    # Un pequeño margen evita que la última línea quede cortada.
    rect.x0 = max(page.rect.x0, rect.x0 - 1)
    rect.y0 = max(page.rect.y0, rect.y0 - 1)
    rect.x1 = min(page.rect.x1, rect.x1 + 1)
    rect.y1 = min(page.rect.y1, rect.y1 + 1)

    opciones = dict(
        color=color,
        align=alineacion,
        lineheight=1.08,
        fontname=nombre_fuente or "helv",
    )

    tamano = max(tamano, 3.5)
    for _ in range(60):
        sobra = page.insert_textbox(rect, texto, fontsize=tamano, **opciones)
        if sobra >= 0:
            return tamano
        tamano *= 0.92
        if tamano < 3.6:
            # Último intento al tamaño mínimo: insert_textbox escribe lo que quepa.
            page.insert_textbox(rect, texto, fontsize=3.5, **opciones)
            return 3.5
    return tamano


def _preparar_traduccion(
    bloques: list[Bloque],
) -> tuple[list[str], list[tuple[str, int, int]]]:
    """Aplana los bloques en unidades de traducción.

    Las tablas y los índices se traducen línea a línea para conservar
    la posición de cada celda; el resto, como párrafos completos.
    """
    unidades: list[str] = []
    mapa: list[tuple[str, int, int]] = []
    for bloque in bloques:
        if bloque.tabular:
            inicio = len(unidades)
            unidades.extend(linea.texto for linea in bloque.lineas)
            mapa.append(("lineas", inicio, len(bloque.lineas)))
        else:
            mapa.append(("bloque", len(unidades), 1))
            unidades.append(bloque.texto)
    return unidades, mapa


def traducir_pagina(
    page: pymupdf.Page,
    traductor: Traductor,
    fuente: Path | None,
    bloques: list[Bloque] | None = None,
) -> tuple[str, int]:
    """Traduce una página y la reconstruye. Devuelve (texto, nº de bloques)."""
    if bloques is None:
        bloques = extraer_bloques(page)
    if not bloques:
        return "", 0

    unidades, mapa = _preparar_traduccion(bloques)
    traducciones = traductor.traducir_bloques(unidades)

    for bloque in bloques:
        r = pymupdf.Rect(bloque.rect)
        r.x0 -= 1
        r.y0 -= 1
        r.x1 += 1
        r.y1 += 1
        page.add_redact_annot(r, fill=None, cross_out=False)

    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
    )

    nombre_fuente = _registrar_fuente(page, fuente)
    partes: list[str] = []

    for bloque, (tipo, inicio, cantidad) in zip(bloques, mapa):
        if tipo == "lineas":
            for desplazamiento, linea in enumerate(bloque.lineas):
                texto = traducciones[inicio + desplazamiento]
                if texto.strip():
                    _insertar_texto(
                        page,
                        linea.rect,
                        texto,
                        linea.tamano,
                        linea.color,
                        linea.alineacion,
                        nombre_fuente,
                    )
            partes.append("\n".join(traducciones[inicio : inicio + cantidad]))
        else:
            texto = traducciones[inicio]
            if texto.strip():
                _insertar_texto(
                    page,
                    bloque.rect,
                    texto,
                    bloque.tamano,
                    bloque.color,
                    bloque.alineacion,
                    nombre_fuente,
                )
            partes.append(texto)

    return "\n\n".join(partes), len(bloques)


# --------------------------------------------------------------------------
# Proceso completo sobre un documento
# --------------------------------------------------------------------------


def resumen_documento(doc: pymupdf.Document) -> dict:
    paginas_con_texto = 0
    total_bloques = 0
    for page in doc:
        bloques = extraer_bloques(page)
        if bloques:
            paginas_con_texto += 1
            total_bloques += len(bloques)
    return {
        "paginas": doc.page_count,
        "paginas_con_texto": paginas_con_texto,
        "bloques": total_bloques,
    }
