# Traductor de PDF

Aplicación web que traduce archivos PDF **manteniendo el diseño original**:
borra el texto de cada bloque y escribe la traducción en el mismo espacio,
reduciendo el tamaño de letra lo justo para que quepa.

Puede funcionar **en tu equipo** (doble clic en `iniciar.bat`) o **publicada en
internet**. Solo el texto se envía al motor de traducción que elijas.

> **¿Quieres usarla en línea?**
>
> - **Recomendado:** **[DESPLIEGUE-RENDER.md](DESPLIEGUE-RENDER.md)** — gratis y
>   sin tarjeta, con GitHub. Funciona con cualquier dominio, incluido el de
>   GoDaddy.
> - **[DESPLIEGUE-GODADDY.md](DESPLIEGUE-GODADDY.md)** — solo si tu plan de
>   GoDaddy tiene cPanel con **Setup Python App**. Los planes solo PHP (como el
>   de WordPress) **no pueden ejecutar Flask**.

## Cómo conserva el formato

1. Extrae cada bloque de texto y su posición exacta en la página.
2. Borra el texto original sin tocar las imágenes ni los fondos.
3. Escribe la traducción en el mismo espacio, reduciendo el tamaño de letra
   hasta que encaje.
4. En tablas, índices y bloques de líneas cortas, traduce y recoloca cada
   línea por separado para no deshacer las columnas.

---

## Cómo empezar

1. Doble clic en **`iniciar.bat`**.
2. La primera vez crea un entorno virtual e instala las dependencias
   (PyMuPDF, Flask y requests). Puede tardar un par de minutos.
3. Se abre el navegador en `http://127.0.0.1:5000`.
4. Arrastra un PDF, elige los idiomas y pulsa **Traducir PDF**.
5. Descarga el PDF traducido o revísalo en la vista previa.

Para detener la aplicación, cierra la ventana negra o pulsa `Ctrl+C`.

> Requisito: Python 3.10 o superior con la opción **Add python.exe to PATH**
> marcada durante la instalación.
>
> Después de la primera instalación, `iniciar.bat` arranca sin conexión;
> solo la traducción necesita internet.

---

## Motores de traducción

| Motor | Clave | Límites | Cuándo usarlo |
|---|---|---|---|
| **Automático** | No | Hereda del motor que funcione | Opción por defecto: prueba Google y cae a MyMemory |
| **Google** | No | Puede devolver HTTP 429 si traduces mucho | Documentos largos cuando funciona |
| **MyMemory** | No | ~5000 palabras/día por IP; 450 caracteres por petición | Alternativa gratuita sin registro |
| **DeepL** | Sí (`:fx` para el plan gratuito) | 500 000 caracteres/mes en el plan gratuito | Mejor calidad y documentos importantes |
| **LibreTranslate** | Opcional | Depende de tu servidor | Privacidad total: alojas tú el motor |

El idioma de origen se puede dejar en **Detectar automáticamente**. Si el motor
elegido no admite detección (MyMemory), la app hace una estimación por palabras
frecuentes y la muestra en el resumen del resultado.

### Privacidad

- El PDF se guarda en la carpeta local `datos/` del proyecto (o en la carpeta
  de temporales si esa no se puede escribir). En Render se usa `/tmp`, que se
  borra al reiniciar o dormir el servicio.
- El texto de cada bloque sí se envía al motor de traducción elegido
  (Google, MyMemory, DeepL o tu LibreTranslate).
- Los trabajos se borran automáticamente a las 24 horas (o antes, si el
  servicio se reinicia y el disco es temporal).
- Las claves API se usan solo durante la petición; no se guardan en disco.

---

## Publicar en internet

### Opción recomendada: Render (gratis)

Guía paso a paso: **→ [DESPLIEGUE-RENDER.md](DESPLIEGUE-RENDER.md)**

Resumen:

1. Crea una cuenta de GitHub y un repositorio.
2. Sube los archivos del proyecto (sin `.venv` ni `datos`).
3. En Render, crea un **Blueprint** desde ese repositorio; `render.yaml` ya
   trae la configuración.
4. Define `TRADUCTOR_USUARIO` y `TRADUCTOR_CLAVE` para que no sea pública.
5. (Opcional) apunta un subdominio de GoDaddy, por ejemplo
   `traductor.tudominio.com`, con un registro CNAME.

El plan gratuito duerme el servicio a los 15 minutos sin visitas: la siguiente
visita tarda alrededor de un minuto. Los PDFs se borran al reiniciar, así que
descarga el resultado en cuanto esté listo.

### Opción con cPanel/Passenger

Si tu hosting tiene **Setup Python App**, sigue
**[DESPLIEGUE-GODADDY.md](DESPLIEGUE-GODADDY.md)**.

> Un plan de GoDaddy que solo ofrece WordPress y PHP-Fusion no puede ejecutar
> Flask. En ese caso usa Render o cambia de plan.

---

## Configuración

Se controla con variables de entorno; todas son opcionales.

| Variable | Por defecto | Descripción |
|---|---|---|
| `TRADUCTOR_USUARIO` | *(vacío)* | Usuario de acceso HTTP Basic |
| `TRADUCTOR_CLAVE` | *(vacío)* | Contraseña de acceso HTTP Basic |
| `TRADUCTOR_MAX_MB` | `200` | Tamaño máximo del PDF en MB |
| `TRADUCTOR_DATOS` | `datos/` del proyecto | Carpeta donde se guardan los trabajos |

Si defines **usuario y clave**, toda la web (incluidas las descargas) pide
autenticación. Es muy recomendable si la publicación es accesible por internet.

Valores sugeridos en Render:

```
TRADUCTOR_USUARIO=tu_usuario
TRADUCTOR_CLAVE=una-clave-larga
TRADUCTOR_MAX_MB=10
TRADUCTOR_DATOS=/tmp/traductor_pdf
```

```bat
REM Ejemplo en Windows
set TRADUCTOR_USUARIO=mi_usuario
set TRADUCTOR_CLAVE=una-clave-larga
set TRADUCTOR_MAX_MB=50
.venv\Scripts\python.exe app.py
```

---

## Limitaciones conocidas

- **PDF escaneados**: si las páginas son imágenes no hay texto que traducir.
  La app las deja intactas y avisa en el resultado. Necesitarías OCR
  (por ejemplo, Tesseract) antes de traducir.
- **Idiomas con escritura compleja**: árabe, hebreo, persa, hindi y tailandés
  pueden mostrarse con letras separadas o mal ordenadas, porque PyMuPDF no
  aplica conformación de glifos ni bidi.
- **Maquetaciones muy densas**: si la traducción ocupa mucho más que el
  original, la letra se reduce hasta un mínimo de 3,5 pt. En casos extremos
  puede quedar texto cortado.
- **Fuentes**: en Windows se usa Segoe UI / Arial. En el hosting se buscan
  fuentes en la carpeta `fuentes/` (ver `fuentes/LEEME.txt`). El aspecto
  tipográfico puede cambiar respecto al original.
- **Texto en curvas o formularios**: los campos de formulario y el texto
  convertido a vectores no se traducen.
- **Plan gratuito de Render**: 512 MB de RAM, se duerme a los 15 minutos sin
  visitas y borra los archivos al reiniciar. Para documentos grandes o uso
  diario, usa la app local o un plan de pago.

---

## Problemas frecuentes

**«Google rechazó la petición por límite de uso (HTTP 429)»**
Google bloquea peticiones anónimas desde algunas redes. Usa el modo
**Automático** o **MyMemory**, o configura una clave de DeepL.

**«MyMemory agotó la cuota gratuita diaria»**
Su límite es por IP. Espera 24 horas, cambia de red o usa DeepL.

**El puerto 5000 está ocupado**
La app busca automáticamente el siguiente libre. También puedes forzarlo:

```bat
.venv\Scripts\python.exe app.py --puerto 8080
```

**El PDF está protegido con contraseña**
Quita la protección con tu lector de PDF habitual y vuelve a intentarlo.

**Windows muestra un aviso al abrir `iniciar.bat`**
Es normal en scripts descargados. Pulsa «Más información → Ejecutar de todos
modos», o ejecuta `python app.py` desde una consola en esta carpeta.

---

## Uso avanzado

```bat
REM Crear el entorno a mano
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

REM Arrancar sin abrir el navegador y en otro puerto
.venv\Scripts\python.exe app.py --puerto 8080 --sin-navegador
```

### Estructura

```
traductor_pdf/
├─ app.py                 Servidor Flask, trabajos en disco y descargas
├─ traductor.py           Extracción, motores y reconstrucción del PDF
├─ passenger_wsgi.py      Arranque en hosting (cPanel/Passenger)
├─ templates/
│  └─ index.html          Interfaz
├─ static/
│  ├─ estilos.css
│  └─ app.js
├─ fuentes/
│  └─ LEEME.txt           Fuentes opcionales para el hosting
├─ datos/                 Trabajos temporales (se crea sola)
├─ requirements.txt
├─ requirements-render.txt Dependencias + gunicorn para Render
├─ Procfile               Arranque en Render
├─ render.yaml            Configuración del servicio en Render
├─ .python-version        Versión de Python para Render
├─ iniciar.bat            Arranque con doble clic (Windows)
├─ DESPLIEGUE-RENDER.md   Guía para publicarla gratis en Render
├─ DESPLIEGUE-GODADDY.md  Guía para publicarla en GoDaddy
└─ README.md
```

### API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/salud` | Comprueba que el servidor responde |
| `POST` | `/api/traducir` | `multipart/form-data`: `archivo`, `origen`, `destino`, `motor`, `deepl_key`, `libre_url`, `libre_key`. Devuelve `{ "id": "..." }` |
| `GET` | `/api/progreso/<id>` | Estado, página actual, motor usado y avisos |
| `POST` | `/api/cancelar/<id>` | Cancela el trabajo |
| `GET` | `/api/descargar/<id>/pdf` | PDF traducido |
| `GET` | `/api/descargar/<id>/txt` | Texto traducido |
| `GET` | `/api/ver/<id>` | Vista previa en línea |
