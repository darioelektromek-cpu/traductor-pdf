(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const formulario = $("formulario");
  const inputArchivo = $("archivo");
  const zona = $("zona");
  const archivoInfo = $("archivo-info");
  const nombreArchivo = $("nombre-archivo");
  const tamanoArchivo = $("tamano-archivo");
  const quitarArchivo = $("quitar-archivo");

  const selectOrigen = $("origen");
  const selectDestino = $("destino");
  const botonIntercambiar = $("intercambiar");
  const selectMotor = $("motor");
  const camposDeepl = $("campos-deepl");
  const camposLibre = $("campos-libre");
  const notaMotor = $("nota-motor");
  const notaIdioma = $("nota-idioma");

  const botonTraducir = $("boton-traducir");
  const errorFormulario = $("error-formulario");

  const progreso = $("progreso");
  const progresoTitulo = $("progreso-titulo");
  const porcentaje = $("porcentaje");
  const barra = $("barra");
  const barraRelleno = $("barra-relleno");
  const estadoTexto = $("estado-texto");
  const detalleTexto = $("detalle-texto");
  const botonCancelar = $("boton-cancelar");

  const resultado = $("resultado");
  const resumen = $("resumen");
  const aviso = $("aviso");
  const botonPdf = $("boton-pdf");
  const botonTxt = $("boton-txt");
  const botonVer = $("boton-ver");
  const marco = $("marco");
  const botonOtro = $("otro");

  const MAX_MB = Number(formulario.dataset.maxMb || 200);

  let archivoActual = null;
  let trabajoId = null;
  let temporizador = null;
  let cancelando = false;

  // ------------------------------------------------------------------
  // Utilidades
  // ------------------------------------------------------------------

  function formatearTamano(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function mostrar(el, visible) {
    if (!el) return;
    el.classList.toggle("oculto", !visible);
  }

  function mostrarError(texto) {
    errorFormulario.textContent = texto;
    mostrar(errorFormulario, true);
  }

  function limpiarError() {
    errorFormulario.textContent = "";
    mostrar(errorFormulario, false);
  }

  function seleccionarArchivo(archivo) {
    limpiarError();
    if (!archivo) return;

    const esPdf =
      archivo.type === "application/pdf" ||
      archivo.name.toLowerCase().endsWith(".pdf");

    if (!esPdf) {
      mostrarError("El archivo debe ser un PDF.");
      return;
    }
    if (archivo.size > MAX_MB * 1024 * 1024) {
      mostrarError("El PDF supera el límite de " + MAX_MB + " MB.");
      return;
    }

    archivoActual = archivo;
    nombreArchivo.textContent = archivo.name;
    tamanoArchivo.textContent = formatearTamano(archivo.size);
    mostrar(zona, false);
    mostrar(archivoInfo, true);
  }

  function quitarSeleccion() {
    archivoActual = null;
    inputArchivo.value = "";
    mostrar(archivoInfo, false);
    mostrar(zona, true);
  }

  function reiniciarResultado() {
    mostrar(resultado, false);
    marco.removeAttribute("src");
    aviso.textContent = "";
    mostrar(aviso, false);
  }

  // ------------------------------------------------------------------
  // Zona de carga
  // ------------------------------------------------------------------

  zona.addEventListener("click", () => inputArchivo.click());
  zona.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" || evento.key === " ") {
      evento.preventDefault();
      inputArchivo.click();
    }
  });

  inputArchivo.addEventListener("change", () => {
    seleccionarArchivo(inputArchivo.files && inputArchivo.files[0]);
  });

  quitarArchivo.addEventListener("click", quitarSeleccion);

  ["dragenter", "dragover"].forEach((tipo) => {
    zona.addEventListener(tipo, (evento) => {
      evento.preventDefault();
      zona.classList.add("arrastrando");
    });
  });

  ["dragleave", "dragend"].forEach((tipo) => {
    zona.addEventListener(tipo, () => zona.classList.remove("arrastrando"));
  });

  zona.addEventListener("drop", (evento) => {
    evento.preventDefault();
    zona.classList.remove("arrastrando");
    const archivo = evento.dataTransfer.files && evento.dataTransfer.files[0];
    seleccionarArchivo(archivo);
  });

  // Evita que el navegador abra el PDF si se suelta fuera de la zona.
  window.addEventListener("dragover", (evento) => evento.preventDefault());
  window.addEventListener("drop", (evento) => evento.preventDefault());

  // ------------------------------------------------------------------
  // Idiomas
  // ------------------------------------------------------------------

  const AVISOS_IDIOMA = {
    ar: "El árabe no se compone correctamente en PDF sin un motor de tipografía avanzado: el texto puede verse con letras separadas.",
    he: "El hebreo puede verse con el orden o la forma de las letras alterados por limitaciones del PDF.",
    fa: "El persa puede verse con letras separadas o desordenadas por limitaciones del PDF.",
    hi: "El hindi puede no mostrarse correctamente por limitaciones de composición tipográfica del PDF.",
    th: "El tailandés puede no mostrarse correctamente por limitaciones de composición tipográfica del PDF.",
  };

  function actualizarIdioma() {
    const codigo = selectDestino.value;
    const aviso = AVISOS_IDIOMA[codigo];
    if (aviso) {
      notaIdioma.textContent = aviso;
      notaIdioma.classList.add("alerta");
      mostrar(notaIdioma, true);
    } else {
      mostrar(notaIdioma, false);
    }
    botonIntercambiar.disabled = selectOrigen.value === "auto";
  }

  selectDestino.addEventListener("change", actualizarIdioma);
  selectOrigen.addEventListener("change", actualizarIdioma);

  botonIntercambiar.addEventListener("click", () => {
    if (selectOrigen.value === "auto") return;
    const origen = selectOrigen.value;
    selectOrigen.value = selectDestino.value;
    selectDestino.value = origen;
    actualizarIdioma();
  });

  // ------------------------------------------------------------------
  // Motor
  // ------------------------------------------------------------------

  selectMotor.addEventListener("change", () => {
    mostrar(camposDeepl, selectMotor.value === "deepl");
    mostrar(camposLibre, selectMotor.value === "libre");

    const textos = {
      auto: "El modo automático intenta Google y, si falla, usa MyMemory.",
      google: "Sin clave. Puede limitar las peticiones si traduces documentos muy largos.",
      mymemory: "Gratuito y sin clave, pero con límite diario por IP y textos de 450 caracteres.",
      deepl: "Requiere una clave API de DeepL. Se usa solo durante esta traducción.",
      libre: "Requiere la URL de un servidor LibreTranslate accesible.",
    };
    notaMotor.textContent = textos[selectMotor.value] || "";
  });

  // ------------------------------------------------------------------
  // Envío y seguimiento
  // ------------------------------------------------------------------

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    limpiarError();

    if (!archivoActual) {
      mostrarError("Primero selecciona un PDF.");
      zona.focus();
      return;
    }

    cancelando = false;
    trabajoId = null;
    reiniciarResultado();

    const datos = new FormData(formulario);
    datos.set("archivo", archivoActual, archivoActual.name);

    botonTraducir.disabled = true;
    mostrar(progreso, true);
    progresoTitulo.textContent = "Traduciendo…";
    estadoTexto.style.color = "";
    estadoTexto.textContent = "Subiendo el documento…";
    detalleTexto.textContent = "";
    porcentaje.textContent = "0 %";
    barraRelleno.style.width = "0%";
    barra.setAttribute("aria-valuenow", "0");
    mostrar(botonCancelar, true);
    botonCancelar.disabled = false;
    progreso.scrollIntoView({ behavior: "smooth", block: "center" });

    fetch("/api/traducir", { method: "POST", body: datos })
      .then(async (respuesta) => {
        const cuerpo = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok) {
          throw new Error(cuerpo.error || "No se pudo iniciar la traducción.");
        }
        return cuerpo;
      })
      .then((cuerpo) => {
        trabajoId = cuerpo.id;
        temporizador = setInterval(consultarProgreso, 800);
      })
      .catch((error) => {
        terminarConError(error.message);
      });
  });

  function consultarProgreso() {
    if (!trabajoId) return;

    fetch("/api/progreso/" + trabajoId, { cache: "no-store" })
      .then((respuesta) => {
        if (!respuesta.ok) throw new Error("Se perdió el contacto con el servidor.");
        return respuesta.json();
      })
      .then((datos) => {
        if (datos.estado === "listo") {
          finalizarTrabajo(datos);
          return;
        }
        if (datos.estado === "error" || datos.estado === "cancelado") {
          terminarConError(datos.error || datos.mensaje || "La traducción falló.");
          return;
        }

        const total = datos.total || 0;
        const pagina = datos.pagina || 0;
        const pct = total ? Math.min(100, Math.round((pagina / total) * 100)) : 0;

        barraRelleno.style.width = Math.max(pct, 4) + "%";
        barra.setAttribute("aria-valuenow", String(pct));
        porcentaje.textContent = total ? pct + " %" : "…";
        estadoTexto.textContent = datos.mensaje || "Trabajando…";

        const piezas = [];
        if (total) piezas.push("Página " + pagina + " de " + total);
        if (datos.motor) piezas.push("Motor: " + datos.motor);
        if (datos.bloques) piezas.push(datos.bloques + " bloques traducidos");
        detalleTexto.textContent = piezas.join(" · ");
      })
      .catch((error) => terminarConError(error.message));
  }

  function finalizarTrabajo(datos) {
    detenerTemporizador();
    mostrar(progreso, false);
    botonTraducir.disabled = false;

    const piezas = [];
    if (datos.total) piezas.push(datos.total + (datos.total === 1 ? " página" : " páginas"));
    if (datos.motor) piezas.push("motor: " + datos.motor);
    if (datos.idioma_detectado) piezas.push("idioma detectado: " + datos.idioma_detectado.toLowerCase());
    resumen.textContent = piezas.join(" · ") || "PDF traducido correctamente.";

    botonPdf.href = "/api/descargar/" + datos.id + "/pdf";
    botonPdf.setAttribute("download", datos.nombre_pdf || "traducido.pdf");
    botonTxt.href = "/api/descargar/" + datos.id + "/txt";
    botonVer.href = "/api/ver/" + datos.id;

    if (datos.aviso) {
      aviso.textContent = datos.aviso;
      mostrar(aviso, true);
    } else {
      mostrar(aviso, false);
    }

    marco.src = "/api/ver/" + datos.id + "?v=" + Date.now();
    mostrar(resultado, true);
    resultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function terminarConError(mensaje) {
    detenerTemporizador();
    botonTraducir.disabled = false;
    mostrar(botonCancelar, false);

    progresoTitulo.textContent = cancelando ? "Cancelado" : "No se pudo traducir";
    estadoTexto.style.color = "var(--error)";
    estadoTexto.textContent = mensaje || "Ocurrió un error inesperado.";
    detalleTexto.textContent = "";
    barraRelleno.style.width = "0%";
    porcentaje.textContent = "";
    cancelando = false;
  }

  function detenerTemporizador() {
    if (temporizador) {
      clearInterval(temporizador);
      temporizador = null;
    }
  }

  botonCancelar.addEventListener("click", () => {
    if (!trabajoId) return;
    cancelando = true;
    botonCancelar.disabled = true;
    estadoTexto.textContent = "Cancelando el trabajo…";
    fetch("/api/cancelar/" + trabajoId, { method: "POST" }).catch(() => {});
  });

  botonOtro.addEventListener("click", () => {
    quitarSeleccion();
    reiniciarResultado();
    mostrar(progreso, false);
    limpiarError();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  // Estado inicial
  actualizarIdioma();
})();
