# Publicar el traductor en Render (gratis)

Esta guía deja la aplicación funcionando en internet con una dirección pública,
sin depender de tu hosting de GoDaddy (que es solo PHP y no puede ejecutar Flask).

Render es un servicio de alojamiento que ejecuta Python gratis. La aplicación
funcionará igual que en tu equipo: subes un PDF, se traduce y lo descargas.

> **Resumen:** el código vive en GitHub y Render lo copia y lo arranca. Cada vez
> que cambies algo en GitHub, Render vuelve a publicar la versión nueva.

---

## Lo que necesitas

1. Una cuenta de **GitHub** (gratis): <https://github.com/signup>
2. Una cuenta de **Render** (gratis y sin tarjeta): <https://dashboard.render.com/register>
3. El archivo **`traductor_pdf.zip`** de este proyecto.

No hace falta instalar nada en tu equipo. Todo se hace desde el navegador.

> Render puede pedirte verificar el correo. No pide tarjeta para el plan
> gratuito. Si algún día añades una, solo se cobra lo que contrates.

---

## 1. Crear el repositorio en GitHub

1. Entra en <https://github.com> e inicia sesión.
2. Arriba a la derecha pulsa **+** → **New repository**.
3. Rellena:

   | Campo | Valor |
   |---|---|
   | **Repository name** | `traductor-pdf` |
   | **Description** | Traductor de PDF con formato original |
   | **Visibility** | **Private** (recomendado) o Public |
   | **Add a README file** | Sin marcar |

4. Pulsa **Create repository**.

Verás una página con instrucciones y un botón **uploading an existing file**.

---

## 2. Subir los archivos

### 2.1 Preparar la carpeta

1. Descomprime **`traductor_pdf.zip`** en tu equipo.
2. Abre la carpeta `traductor_pdf`.
3. **No subas** estas carpetas:
   - `.venv` (entorno virtual de Windows)
   - `datos` (trabajos temporales)
   - `__pycache__`

### 2.2 Subirlos a GitHub

1. En la página del repositorio, pulsa el enlace
   **uploading an existing file**.
   (Si no lo ves: **Add file** → **Upload files**.)
2. Abre la carpeta `traductor_pdf` en el Explorador de Windows.
3. Selecciona **todo el contenido** con `Ctrl+E`, no la carpeta en sí, y
   arrástralo a la zona de subida del navegador.

   Deben quedar en la **raíz** del repositorio, así:

   ```
   traductor-pdf/
   ├─ app.py
   ├─ traductor.py
   ├─ requirements.txt
   ├─ requirements-render.txt
   ├─ Procfile
   ├─ render.yaml
   ├─ .python-version
   ├─ passenger_wsgi.py
   ├─ iniciar.bat
   ├─ README.md
   ├─ DESPLIEGUE-GODADDY.md
   ├─ DESPLIEGUE-RENDER.md
   ├─ templates/
   ├─ static/
   └─ fuentes/
   ```

   > **Importante:** si arrastras la carpeta `traductor_pdf` entera, GitHub la
   > mete dentro de otra carpeta y Render no encontrará `render.yaml` en la
   > raíz. En ese caso, entra en la carpeta en GitHub, selecciona los archivos y
   > usa **Move** para subirlos un nivel; o indica `Root Directory:
   > traductor_pdf` al crear el servicio (paso 3.2).

4. En **Commit changes** escribe `Primera versión` y pulsa **Commit changes**.

### 2.3 Si `.python-version` no aparece

Es un archivo oculto para algunos selectores. No es imprescindible: en el paso 3
puedes crear la variable de entorno `PYTHON_VERSION` con valor `3.11.9`.
Si aparece en GitHub, perfecto.

---

## 3. Crear el servicio en Render

Tienes dos caminos. **El A es el más rápido** porque lee `render.yaml`.

### Opción A: Blueprint (recomendado)

1. Entra en <https://dashboard.render.com>.
2. Pulsa **New +** → **Blueprint**.
3. Conecta tu cuenta de GitHub si es la primera vez y autoriza el repositorio
   `traductor-pdf`.
4. Selecciona el repositorio y pulsa **Connect**.
5. Render detecta `render.yaml` y muestra el servicio **traductor-pdf**.
   Pulsa **Apply**.

Render pedirá los valores de las variables marcadas como secretas:

| Variable | Qué poner |
|---|---|
| `TRADUCTOR_USUARIO` | El usuario que quieras, por ejemplo `familia` |
| `TRADUCTOR_CLAVE` | Una contraseña larga, por ejemplo `Traductor-2026-xyz` |

> **Escribe usuario y contraseña siempre.** La dirección será pública y
> cualquiera que la encuentre podría usar tu aplicación y gastar la cuota de
> traducción. Apúntalos: el navegador te los pedirá al entrar.

6. Espera a que termine el despliegue (unos 2–5 minutos la primera vez).

### Opción B: Web Service manual

Si prefieres no usar Blueprint:

1. **New +** → **Web Service**.
2. Conecta el repositorio `traductor-pdf`.
3. Rellena:

   | Campo | Valor |
   |---|---|
   | **Name** | `traductor-pdf` |
   | **Language** | `Python 3` |
   | **Region** | `Frankfurt (EU Central)` (la más cercana a España) |
   | **Branch** | `main` |
   | **Root Directory** | *(vacío)*, salvo que los archivos estén dentro de una carpeta: `traductor_pdf` |
   | **Build Command** | `pip install --upgrade pip && pip install -r requirements-render.txt` |
   | **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180 --access-logfile - --error-logfile -` |
   | **Instance Type** | `Free` |

4. En **Environment Variables** añade:

   | Variable | Valor |
   |---|---|
   | `TRADUCTOR_USUARIO` | tu usuario |
   | `TRADUCTOR_CLAVE` | tu contraseña |
   | `TRADUCTOR_MAX_MB` | `10` |
   | `TRADUCTOR_DATOS` | `/tmp/traductor_pdf` |
   | `PYTHON_VERSION` | `3.11.9` (opcional) |

5. En **Advanced** → **Health Check Path** escribe `/api/salud`.
6. Pulsa **Create Web Service**.

---

## 4. Comprobar que funciona

1. En Render, arriba del servicio verás la dirección, parecida a:

   ```
   https://traductor-pdf.onrender.com
   ```

   (Si el nombre estaba ocupado, Render añade un sufijo aleatorio.)

2. Abre en el navegador:

   ```
   https://traductor-pdf.onrender.com/api/salud
   ```

   Debe responder algo como:

   ```json
   {"ok": true, "version": "1.28.2", "almacen": "/tmp/traductor_pdf"}
   ```

   La primera visita puede tardar **hasta un minuto**: Render está despertando
   el servicio.

3. Abre la página principal, introduce usuario y contraseña y traduce un PDF
   pequeño de prueba (2–3 páginas).

> **Consejo:** si el navegador te pide usuario y contraseña, escríbelos tal cual
> los definiste. Si te equivocas, borra las credenciales guardadas del sitio o
> prueba en una ventana privada.

---

## 5. Usar tu dominio de GoDaddy (opcional)

Puedes tener una dirección bonita, por ejemplo
`https://traductor.tudominio.com`, sin dejar de usar GoDaddy para el dominio.

> Esto **no afecta** a tu web actual de GoDaddy: solo añade un subdominio nuevo.

### 5.1 Añadir el dominio en Render

1. En Render, entra en el servicio → **Settings**.
2. Baja hasta **Custom Domains** → **+ Add Custom Domain**.
3. Escribe `traductor.tudominio.com` (con tu dominio real) y pulsa **Save**.
4. Render te mostrará el destino que debes usar, por ejemplo
   `traductor-pdf.onrender.com`. Cópialo.

### 5.2 Crear el registro DNS en GoDaddy

1. Entra en <https://godaddy.com> → **Mi cuenta** → **Mis productos**.
2. En tu dominio pulsa **DNS** (o **Administrar DNS**).
3. Pulsa **Add New Record** / **Añadir registro** y rellena:

   | Campo | Valor |
   |---|---|
   | **Type** | `CNAME` |
   | **Name** | `traductor` |
   | **Value** | `traductor-pdf.onrender.com` |
   | **TTL** | `1/2 hour` o `600` |

4. Guarda. Si existía otro registro con el nombre `traductor`, bórralo antes.
   **No borres** los registros del dominio principal (`@` ni `www`).

### 5.3 Verificar en Render

1. Vuelve a Render → **Settings** → **Custom Domains**.
2. Pulsa **Verify** junto a tu dominio.
3. Si falla, espera 5–15 minutos (el DNS tarda en propagarse) y reintenta.
4. Cuando aparezca como verificado, Render emite el certificado HTTPS solo.
   Abre `https://traductor.tudominio.com` y comprueba que carga.

> Para el dominio principal (`tudominio.com`) Render usa un registro `A` con
> valor `216.24.57.1`, pero eso **movería tu web entera**. Usa un subdominio.

---

## 6. Actualizar la aplicación

Cada cambio en GitHub se publica solo:

1. En GitHub, abre el archivo (por ejemplo `traductor.py`).
2. Pulsa el lápiz (**Edit**) y guarda con **Commit changes**.
3. Render detecta el cambio y vuelve a desplegar en 1–3 minutos.

También puedes volver a **Add file** → **Upload files** y subir los archivos
modificados (se sobrescriben).

---

## 7. Límites del plan gratuito (importante)

| Límite | Qué significa para ti |
|---|---|
| **512 MB de RAM y 0,1 CPU** | PDFs de hasta ~10 MB y no muy largos. Empieza con documentos de menos de 30–40 páginas. |
| **Se duerme a los 15 min sin visitas** | La siguiente visita tarda ~1 minuto en despertar. Es normal. |
| **Disco efímero** | Al dormirse, reiniciarse o republicar, **se borran los PDFs** de `/tmp`. Descarga el resultado en cuanto termine. |
| **750 horas de instancia al mes** | Suficiente para un servicio. Si se agotan, se suspende hasta el mes siguiente. |
| **5 GB de tráfico al mes** | De sobra para uso personal. |
| **Sin disco persistente** | No se pueden guardar archivos entre reinicios. La app ya está preparada para trabajos temporales. |
| **IP compartida** | Google puede responder **HTTP 429**. Usa el motor **Automático** o **MyMemory**. |

### Recomendaciones

- Configura **usuario y contraseña** (paso 3). Sin ellos, la web es pública.
- No cierres la pestaña mientras se traduce un documento largo.
- Si un trabajo se interrumpe porque Render reinició el servicio, vuelve a
  intentarlo con un PDF más pequeño.
- Para uso intensivo o sin esperas, el plan de pago más barato de Render cuesta
  unos **7 USD/mes** y mantiene el servicio siempre despierto.

---

## 8. Problemas frecuentes

**El despliegue falla con «Build failed»**
Abre **Logs** y revisa la última línea. Casi siempre es la versión de Python o
una dependencia. Solución habitual: añade la variable `PYTHON_VERSION` con
`3.11.9` y pulsa **Manual Deploy → Deploy latest commit**.

**«Exited with status 1» al arrancar**
Comprueba que el **Start Command** es exactamente el del paso 3 y que
`app.py` está en la raíz del repositorio. Si los archivos están en una carpeta,
indica `Root Directory: traductor_pdf`.

**Error 502 o la página no carga**
Puede ser el arranque en frío. Espera un minuto y recarga. Si sigue, mira
**Logs** y comprueba `/api/salud`.

**«El archivo supera el límite de 10 MB»**
Es el límite configurado. Puedes subirlo cambiando `TRADUCTOR_MAX_MB`, pero con
512 MB de RAM no conviene pasar de 15–20.

**«Google rechazó la petición por límite de uso (HTTP 429)»**
Normal en servidores compartidos. Elige **Automático** (cae a MyMemory) o
**MyMemory**, o configura una clave de **DeepL**.

**«MyMemory agotó la cuota gratuita diaria»**
Su límite es por IP y en Render la comparten varios usuarios. Espera 24 horas o
usa DeepL.

**El trabajo se interrumpe a mitad**
Render reinició o durmió el servicio. Vuelve a intentarlo con menos páginas.
Si pasa siempre en la misma página, puede ser falta de memoria.

**La descarga da 404 después de un rato**
El PDF se borró al reiniciarse el servicio (disco efímero). Descarga antes.

**La web pide usuario y contraseña y no entra**
Comprueba que `TRADUCTOR_USUARIO` y `TRADUCTOR_CLAVE` están **las dos** puestas
(sin una de ellas, la autenticación se desactiva). Cambia los valores en
**Environment** y pulsa **Save Changes**; Render reinicia solo.

**Quiero ver los registros**
En Render, pestaña **Logs**. Ahí aparecen las traducciones, errores y reinicios.

---

## 9. Alternativas si no quieres usar GitHub

Render necesita un repositorio Git, así que GitHub (o GitLab/Bitbucket) es
obligatorio. Si no quieres crearlo:

| Servicio | Ventaja | Inconveniente |
|---|---|---|
| **PythonAnywhere** | Gratis, siempre despierto, sin Git | 512 MB de disco, más lento; se sube por navegador |
| **Hugging Face Spaces** | Gratis, se sube por navegador | Pensado para demos; límites de uso |
| **Railway** | Muy fácil | Pide tarjeta tras la prueba |
| **Tu equipo con `iniciar.bat`** | Sin límites ni esperas | Solo funciona con el equipo encendido |

Si prefieres PythonAnywhere, el arranque es con `passenger_wsgi.py` o con
`gunicorn app:app`, igual que en GoDaddy.

---

## Lista rápida

- [ ] Cuenta de GitHub creada.
- [ ] Repositorio `traductor-pdf` creado.
- [ ] Archivos subidos **en la raíz** (sin `.venv` ni `datos`).
- [ ] Servicio creado en Render (Blueprint u manual).
- [ ] `TRADUCTOR_USUARIO` y `TRADUCTOR_CLAVE` configurados.
- [ ] `TRADUCTOR_MAX_MB=10` y `TRADUCTOR_DATOS=/tmp/traductor_pdf`.
- [ ] `/api/salud` responde `ok: true`.
- [ ] PDF de prueba traducido y descargado.
- [ ] (Opcional) subdominio `traductor.tudominio.com` verificado en Render.
