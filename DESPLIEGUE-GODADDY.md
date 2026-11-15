# Publicar el traductor en GoDaddy

Esta guía sirve para dejar la aplicación funcionando en tu hosting de GoDaddy y
usarla desde cualquier navegador.

> **Requisito imprescindible:** tu plan debe tener cPanel con la opción
> **«Setup Python App»** (a veces aparece como **«Setup Python App»** o
> **«Python App»** dentro de la sección *Software*).
>
> Si no aparece esa opción, el plan es solo PHP y **no puede ejecutar Flask**.
> En ese caso mira el apartado [Si no tienes «Setup Python App»](#si-no-tienes-setup-python-app).

---

## 1. Comprobar que tu plan sirve

1. Entra en <https://godaddy.com> → **Mi cuenta** → **Mis productos**.
2. En tu **Web Hosting**, pulsa **Administrar** (abre cPanel).
3. Busca en cPanel la sección **Software** → **Setup Python App**.

Si la ves, continúa. Si no, salta al final de esta guía.

---

## 2. Crear la aplicación Python en cPanel

1. Abre **Setup Python App** → **Create Application**.
2. Rellena:

   | Campo | Valor |
   |---|---|
   | **Python version** | La más alta disponible (3.11 o 3.12 son las más seguras) |
   | **Application root** | `traductor` |
   | **Application URL** | Tu dominio o un subdominio, por ejemplo `traductor.tudominio.com` |
   | **Application startup file** | `passenger_wsgi.py` |
   | **Application Entry point** | `application` |

3. Pulsa **Create**.

cPanel creará una carpeta `traductor` en tu cuenta y un entorno virtual propio.
También generará un `passenger_wsgi.py`; más adelante lo reemplazamos por el
nuestro.

> Si prefieres no usar un subdominio, puedes publicarlo en una ruta como
> `tudominio.com/traductor`. Funciona igual.

---

## 3. Subir los archivos

1. En cPanel abre **File Manager** (Administrador de archivos).
2. Entra en la carpeta de la aplicación: `/home/TU_USUARIO/traductor`.
3. Sube el archivo **`traductor_pdf.zip`** (botón **Upload**).
4. Vuelve a la carpeta, haz clic derecho sobre el ZIP → **Extract**.
5. Comprueba que los archivos quedan **directamente** en `traductor/`:

   ```
   traductor/
   ├─ app.py
   ├─ traductor.py
   ├─ passenger_wsgi.py
   ├─ requirements.txt
   ├─ iniciar.bat          (solo Windows, puedes dejarlo)
   ├─ README.md
   ├─ DESPLIEGUE-GODADDY.md
   ├─ templates/
   ├─ static/
   ├─ fuentes/
   └─ datos/               (se crea sola)
   ```

   Si al extraer se crea una subcarpeta `traductor_pdf/`, entra en ella, selecciona
   todo y muévelo un nivel arriba.

6. **No subas** la carpeta `.venv`: el hosting crea su propio entorno.

---

## 4. Instalar las dependencias

Tienes dos formas. Usa la que te muestre tu cPanel.

### Opción A: Terminal de cPanel

1. cPanel → **Terminal** (o **Advanced → Terminal**).
2. Copia y ejecuta el comando que muestra **Setup Python App** en el apartado
   *«Enter to the virtual environment»*. Se parece a:

   ```bash
   source /home/TU_USUARIO/virtualenv/traductor/3.11/bin/activate && cd /home/TU_USUARIO/traductor
   ```

3. Instala las dependencias:

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Opción B: Sin terminal

En **Setup Python App**, dentro de la aplicación, busca la sección
**«Add dependencies»** o **«Configuration files»** y añade una por una:

```
Flask
PyMuPDF
requests
```

Guarda los cambios. cPanel las instalará en el entorno virtual.

---

## 5. Configurar variables de entorno (muy recomendable)

En la misma pantalla de **Setup Python App**, busca
**«Environment variables»** / **«Add variable»** y crea estas:

| Variable | Ejemplo | Para qué |
|---|---|---|
| `TRADUCTOR_USUARIO` | `mi_usuario` | Usuario para entrar a la web |
| `TRADUCTOR_CLAVE` | `una-clave-larga-y-secreta` | Contraseña de acceso |
| `TRADUCTOR_MAX_MB` | `20` | Tamaño máximo de PDF en el hosting |
| `TRADUCTOR_DATOS` | `/home/TU_USUARIO/traductor/datos` | Carpeta de trabajos |

- Si defines **usuario y clave**, la web pedirá usuario y contraseña al abrirla.
  **Es muy recomendable** porque la URL será pública.
- Si no defines usuario/clave, cualquiera con el enlace podría usar tu aplicación.
- `TRADUCTOR_MAX_MB`: en hosting compartido conviene `15` o `20` MB.
- `TRADUCTOR_DATOS` debe ser una carpeta con permisos de escritura
  (normalmente `755` o `775`).

---

## 6. Reemplazar el arranque de Passenger

cPanel genera su propio `passenger_wsgi.py`. Sustitúyelo por el del proyecto:

1. En **File Manager**, entra en `traductor/`.
2. Si existe `passenger_wsgi.py`, haz una copia y luego edítalo.
3. Deja exactamente este contenido:

   ```python
   import os
   import sys

   BASE_DIR = os.path.dirname(os.path.abspath(__file__))
   if BASE_DIR not in sys.path:
       sys.path.insert(0, BASE_DIR)

   os.chdir(BASE_DIR)

   from app import app as application
   ```

   Ese es el archivo `passenger_wsgi.py` que ya viene en el ZIP, así que también
   puedes simplemente volver a subirlo para sobrescribir.

---

## 7. Reiniciar y comprobar

1. En **Setup Python App**, pulsa **Restart**.
   Si no ves el botón, crea o toca el archivo `tmp/restart.txt`:

   ```bash
   mkdir -p /home/TU_USUARIO/traductor/tmp
   touch /home/TU_USUARIO/traductor/tmp/restart.txt
   ```

2. Abre en el navegador:

   ```
   https://TU_DOMINIO/api/salud
   ```

   Debe responder algo como:

   ```json
   {"ok": true, "version": "1.28.2", "almacen": "/home/TU_USUARIO/traductor/datos"}
   ```

3. Abre la página principal (`https://TU_DOMINIO`) y traduce un PDF de prueba.

---

## 8. Fuentes (opcional, pero útil)

En Windows la app usa Segoe UI/Arial; en el hosting Linux esas fuentes no
existen. Para que el PDF traducido se vea mejor:

1. Abre la carpeta `fuentes/` del proyecto en el hosting.
2. Sube una fuente libre, por ejemplo `DejaVuSans.ttf`
   (<https://dejavu-fonts.github.io/>).
3. Para chino, japonés o coreano sube una fuente CJK, por ejemplo
   `NotoSansCJK-Regular.ttc`
   (<https://fonts.google.com/noto>).

Los nombres reconocidos están explicados en `fuentes/LEEME.txt`.

---

## 9. Limitaciones del hosting compartido

- **Google puede devolver HTTP 429**: las IP compartidas se usan mucho. Usa el
  modo **Automático** (cae a MyMemory) o configura **DeepL**.
- **Memoria y tiempo limitados**: los PDFs muy grandes o de muchas páginas
  pueden agotar el proceso. Empieza con documentos de menos de 20 MB y pocas
  páginas.
- **Passenger puede reiniciar el proceso**: si ocurre en mitad de una
  traducción, verás el aviso *«El trabajo se interrumpió…»*. Vuelve a intentarlo.
- **La primera visita tarda unos segundos**: Passenger arranca la aplicación
  bajo demanda.
- **El trabajo pesado ocurre en el servidor**: no cierres la pestaña mientras
  se traduce un documento largo; el progreso se pierde de vista (aunque el
  trabajo puede seguir).
- **HTTPS**: activa el certificado SSL gratuito de GoDaddy en cPanel
  (*SSL/TLS Status*), sobre todo si usas usuario y contraseña.

### Ajuste opcional de Passenger

Si tu plan permite editar `.htaccess` o la configuración de Passenger y notas
que se abren demasiados procesos, puedes limitar el pool a uno:

```apache
PassengerMaxPoolSize 1
```

No es obligatorio: la aplicación guarda el estado en disco y funciona con
varios procesos.

---

## 10. Actualizar la aplicación

1. Sube los archivos nuevos con **File Manager** (sobrescribiendo).
2. Si cambió `requirements.txt`, repite el `pip install -r requirements.txt`.
3. Reinicia (botón **Restart** o `touch tmp/restart.txt`).

---

## Si no tienes «Setup Python App»

Tu plan es de hosting solo PHP y no ejecutará Flask. Alternativas:

1. **Cambiar de plan** a uno de GoDaddy con Python/cPanel, o a un **VPS**.
2. **Publicarlo gratis en otro servicio** que sí ejecute Python:
   - [Render](https://render.com) (plan gratuito, se duerme por inactividad)
   - [Railway](https://railway.app)
   - [PythonAnywhere](https://www.pythonanywhere.com) (plan gratuito)
3. **Usar la app en tu equipo** con `iniciar.bat` y compartir pantalla/archivos.

En Render, Railway o PythonAnywhere el despliegue es parecido: subir el código,
instalar `requirements.txt` y arrancar con `gunicorn app:app` o con el
`passenger_wsgi.py` equivalente del servicio.

> **Recomendación:** si tu plan es solo PHP, usa
> **[DESPLIEGUE-RENDER.md](DESPLIEGUE-RENDER.md)**. Es gratis, no pide tarjeta y
> el proyecto ya incluye `render.yaml`, `Procfile` y `requirements-render.txt`
> listos para publicar. Después puedes apuntar un subdominio de GoDaddy a Render.

---

## Problemas frecuentes

**Error 500 al abrir la web**
Revisa el log de Passenger (la ruta que indicaste en *Passenger log file*) y
comprueba que `passenger_wsgi.py` importa `app` correctamente y que las
dependencias están instaladas en el entorno virtual.

**`ModuleNotFoundError: No module named 'flask'`**
Las dependencias se instalaron fuera del entorno virtual. Actívalo con el
comando de *«Enter to the virtual environment»* y repite `pip install -r requirements.txt`.

**`PermissionError` en `datos/`**
Da permisos de escritura a la carpeta:

```bash
chmod -R 755 /home/TU_USUARIO/traductor/datos
```

**Error 413 o el PDF no sube**
Baja `TRADUCTOR_MAX_MB` a `10` o `15` y reinicia la aplicación.

**La web pide usuario y contraseña y no lo recuerdo**
Borra o cambia las variables `TRADUCTOR_USUARIO` y `TRADUCTOR_CLAVE` en
**Setup Python App** y reinicia.

**Sigue apareciendo la versión antigua**
Fuerza el reinicio con `touch tmp/restart.txt` y recarga con `Ctrl+F5`.
