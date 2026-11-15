"""
Punto de entrada para el hosting de GoDaddy (cPanel + Passenger).

GoDaddy crea este archivo automáticamente al configurar la aplicación Python.
Si no lo crea, o si lo sobrescribe, deja este contenido.

Documentación: DESPLIEGUE-GODADDY.md
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Algunos planes arrancan Passenger desde otro directorio.
try:
    os.chdir(BASE_DIR)
except OSError:
    pass

from app import app as application  # noqa: E402  (debe ir después de sys.path)
