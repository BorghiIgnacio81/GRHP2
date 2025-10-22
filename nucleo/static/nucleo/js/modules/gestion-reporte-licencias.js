/**
 * Controlador principal para la pantalla de Gestión / Reporte de Licencias.
 * Traslada la lógica inline (filtros, modales y helpers) a un módulo dedicado.
 */
class GestionReporteLicencias {
    constructor(options = {}) {
        this.options = Object.assign({
            autoFilterYear: true,
            urlFiltroBase: window.location.pathname,
            selectorCheckboxRango: '#fecha_rango_chk',
            selectorFechaHasta: '#fecha_hasta',
            containerSelector: '.dashboard-box'
        }, options);

        this.debounceTimers = {};
        this.activeFetchController = null;

        this.cacheElements();
        this.bindEvents();
        this.applyInitialState();
        this.initUIHelpers();
    }

    cacheElements() {
        this.container = document.querySelector(this.options.containerSelector);
        this.checkboxRango = document.querySelector(this.options.selectorCheckboxRango);
        this.inputFechaHasta = document.querySelector(this.options.selectorFechaHasta);
        this.formFiltros = this.container ? this.container.querySelector('form.filtros-form') : document.querySelector('form.filtros-form');
        this.modalRechazo = document.getElementById('modal-rechazo');
        this.modalComentarios = document.getElementById('modal-comentarios');
        this.cerrarModalRechazoBtn = document.getElementById('cerrar-modal-rechazo');
        this.cerrarModalComentariosBtn = document.getElementById('cerrar-modal-comentarios');
        this.cerrarModalComentariosFooterBtn = document.getElementById('cerrar-modal-comentarios-btn');
        this.confirmarRechazoBtn = document.getElementById('confirmar-rechazo');
        this.inputSolicitudId = document.getElementById('modal-solicitud-id');
        this.textareaMotivo = document.getElementById('motivo-rechazo');
        this.contenidoComentarios = document.getElementById('comentarios-contenido');
        this.messageCloseButtons = document.querySelectorAll('.mensaje-cerrable .cerrar-mensaje');
        this.mensajesPrincipales = document.getElementById('mensajes-principales');
        this.formsEliminar = document.querySelectorAll('.form-eliminar');
    this.modalEliminar = document.getElementById('modal-confirmar-eliminacion');
    this.btnCancelarEliminar = document.getElementById('cancelar-eliminacion');
    this.btnConfirmarEliminar = document.getElementById('confirmar-eliminacion');
    this.formPendienteEliminar = null;
        this.exportButtons = document.querySelectorAll('.export-btn');
        this.inputEmpleado = document.getElementById('busqueda-empleado');
        this.hiddenEmpleado = document.getElementById('empleado-filtro');
        this.autocompleteEmpleado = document.getElementById('resultados-autocomplete');
        this.btnLimpiarEmpleado = document.getElementById('limpiar-empleado');
        this.btnLimpiarFiltros = this.formFiltros ? this.formFiltros.querySelector('#limpiar-filtros') : document.getElementById('limpiar-filtros');
    }

    bindEvents() {
        if (this.checkboxRango) {
            this.checkboxRango.addEventListener('change', () => {
                this.updateFechaHasta();
                this.fetchAndRenderResultados();
            });
        }

        if (this.cerrarModalRechazoBtn) {
            this.cerrarModalRechazoBtn.addEventListener('click', () => this.cerrarModal(this.modalRechazo));
        }
        if (this.modalRechazo) {
            this.modalRechazo.addEventListener('click', (event) => {
                if (event.target === this.modalRechazo) {
                    this.cerrarModal(this.modalRechazo);
                }
            });
        }

        if (this.cerrarModalComentariosBtn) {
            this.cerrarModalComentariosBtn.addEventListener('click', () => this.cerrarModal(this.modalComentarios));
        }
        if (this.cerrarModalComentariosFooterBtn) {
            this.cerrarModalComentariosFooterBtn.addEventListener('click', () => this.cerrarModal(this.modalComentarios));
        }
        if (this.modalComentarios) {
            this.modalComentarios.addEventListener('click', (event) => {
                if (event.target === this.modalComentarios) {
                    this.cerrarModal(this.modalComentarios);
                }
            });
        }

        if (this.confirmarRechazoBtn) {
            this.confirmarRechazoBtn.addEventListener('click', () => this.confirmarRechazo());
        }

        // Exponer funciones globales utilizadas por atributos onclick existentes
        window.abrirModalRechazo = (solicitudId) => this.abrirModalRechazo(solicitudId);
        window.abrirModalComentarios = (solicitudId, comentario) => this.abrirModalComentarios(solicitudId, comentario);

        this.bindAutoFilterControls();
        this.bindResetButton();
        this.bindModalEliminarStatics();
    }

    bindResetButton() {
        if (!this.btnLimpiarFiltros) {
            return;
        }
        if (this.btnLimpiarFiltros.dataset.bound === '1') {
            return;
        }
        this.btnLimpiarFiltros.dataset.bound = '1';
        this.btnLimpiarFiltros.addEventListener('click', () => this.resetFiltros());
    }

    resetFiltros() {
        if (!this.formFiltros) {
            return;
        }

        const selects = this.formFiltros.querySelectorAll('select[name]');
        selects.forEach((select) => {
            select.value = '';
        });

        const fechas = this.formFiltros.querySelectorAll('input[type="date"]');
        fechas.forEach((input) => {
            input.value = '';
        });

        if (this.checkboxRango) {
            this.checkboxRango.checked = false;
        }

        if (this.inputEmpleado) {
            this.inputEmpleado.value = '';
        }
        if (this.hiddenEmpleado) {
            this.hiddenEmpleado.value = '';
            this.hiddenEmpleado.dataset.origin = 'manual';
        }
        if (this.autocompleteEmpleado) {
            this.autocompleteEmpleado.innerHTML = '';
            this.autocompleteEmpleado.style.display = 'none';
        }

        this.updateFechaHasta();
        this.fetchAndRenderResultados(this.options.urlFiltroBase);
    }

    applyInitialState() {
        this.updateFechaHasta();
        if (this.options.autoFilterYear) {
            this.aplicarFiltroAnioInicial();
        }
    }

    initUIHelpers() {
        this.bindMessageClosers();
        this.scrollToImportantMessage();
        this.bindDeletionConfirmation();
        this.ensureExportBindings();
    this.initBuscadorEmpleados();
    }

    bindAutoFilterControls() {
        if (!this.formFiltros) {
            return;
        }

        const autoElements = this.formFiltros.querySelectorAll('select[name], input[type="date"]');
        autoElements.forEach((element) => {
            if (element === this.inputEmpleado) {
                return;
            }
            if (element.dataset.autoFilterBound === '1') {
                return;
            }
            element.dataset.autoFilterBound = '1';
            const eventName = element.tagName === 'SELECT' ? 'change' : 'change';
            element.addEventListener(eventName, () => this.fetchAndRenderResultados());
        });
    }

    initBuscadorEmpleados() {
        if (!this.inputEmpleado || !this.hiddenEmpleado) {
            return;
        }

        const limpiarDropdown = () => {
            if (this.autocompleteEmpleado) {
                this.autocompleteEmpleado.style.display = 'none';
                this.autocompleteEmpleado.innerHTML = '';
            }
        };

        const sincronizarHidden = () => {
            if (!this.hiddenEmpleado || !this.inputEmpleado) {
                return;
            }
            const texto = this.inputEmpleado.value.trim();
            this.hiddenEmpleado.value = texto;
            this.hiddenEmpleado.dataset.origin = 'manual';
        };

        const triggerBusqueda = () => {
            sincronizarHidden();
            limpiarDropdown();
            this.fetchAndRenderResultados();
        };

        limpiarDropdown();

        if (this.inputEmpleado) {
            this.inputEmpleado.addEventListener('input', () => {
                sincronizarHidden();
                limpiarDropdown();
                clearTimeout(this.busquedaEmpleadoTimeout);
                this.busquedaEmpleadoTimeout = setTimeout(() => triggerBusqueda(), 350);
            });

            this.inputEmpleado.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    triggerBusqueda();
                }
            });
        }

        if (this.btnLimpiarEmpleado) {
            this.btnLimpiarEmpleado.addEventListener('click', () => {
                if (this.inputEmpleado) {
                    this.inputEmpleado.value = '';
                }
                sincronizarHidden();
                limpiarDropdown();
                this.fetchAndRenderResultados();
            });
        }

        if (this.formFiltros) {
            this.formFiltros.addEventListener('submit', (event) => {
                // Evitar recarga completa: manejamos el submit vía fetch
                event.preventDefault();
                triggerBusqueda();
            });
        }
    }

    async fetchAndRenderResultados(customUrl = null) {
        if (!this.formFiltros) {
            return;
        }

        if (this.activeFetchController) {
            this.activeFetchController.abort();
        }
        this.activeFetchController = new AbortController();

        const formData = new FormData(this.formFiltros);
        formData.delete('csrfmiddlewaretoken');

        if (this.inputFechaHasta && this.inputFechaHasta.hasAttribute('disabled')) {
            formData.delete('fecha_hasta');
        }

        let targetUrl = customUrl;

        if (!targetUrl) {
            const params = new URLSearchParams();
            for (const [key, value] of formData.entries()) {
                if (!value) {
                    continue;
                }
                params.append(key, value);
            }
            params.delete('page');

            const baseUrl = this.options.urlFiltroBase || window.location.pathname;
            targetUrl = params.toString() ? `${baseUrl}?${params.toString()}` : baseUrl;
        }

        try {
            const response = await fetch(targetUrl, {
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                signal: this.activeFetchController.signal
            });

            if (!response.ok) {
                throw new Error(`Error al actualizar la tabla (${response.status})`);
            }

            const html = await response.text();
            this.renderRespuestaDinamica(html);
            this.updateHistory(targetUrl);
        } catch (error) {
            if (error.name === 'AbortError') {
                return;
            }
            console.error('Error actualizando gestión de licencias:', error);
        } finally {
            this.activeFetchController = null;
        }
    }

    renderRespuestaDinamica(html) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const nuevoTbody = doc.querySelector('#tabla-licencias-completa tbody');
        const tbodyActual = document.querySelector('#tabla-licencias-completa tbody');
        if (nuevoTbody && tbodyActual) {
            tbodyActual.innerHTML = nuevoTbody.innerHTML;
        }

        const nuevaTablaExport = doc.querySelector('#tabla-licencias-excel tbody');
        const tablaExportActual = document.querySelector('#tabla-licencias-excel tbody');
        if (nuevaTablaExport && tablaExportActual) {
            tablaExportActual.innerHTML = nuevaTablaExport.innerHTML;
        }

        const paginacionNueva = doc.querySelector('.paginacion');
        const paginacionActual = document.querySelector('.paginacion');
        if (paginacionNueva && paginacionActual) {
            paginacionActual.innerHTML = paginacionNueva.innerHTML;
            this.rebindPagination(paginacionActual);
        }

        const mensajesNuevos = doc.getElementById('mensajes-principales');
        let mensajesActual = document.getElementById('mensajes-principales');
        if (!mensajesActual && mensajesNuevos) {
            mensajesActual = document.createElement('div');
            mensajesActual.id = 'mensajes-principales';
            this.container.appendChild(mensajesActual);
        }
        if (mensajesActual) {
            mensajesActual.innerHTML = mensajesNuevos ? mensajesNuevos.innerHTML : '';
        }

        this.refreshDynamicElements();
    }

    rebindPagination(container) {
        if (!container) {
            return;
        }

        const buttons = Array.from(container.querySelectorAll('button'));
        buttons.forEach((btn) => {
            const onclickAttr = btn.getAttribute('onclick');
            if (onclickAttr && onclickAttr.includes('window.location')) {
                const match = onclickAttr.match(/window\.location\s*=\s*'([^']+)'/);
                if (match) {
                    btn.dataset.pageUrl = match[1];
                }
                btn.removeAttribute('onclick');
            }

            if (btn.disabled || !btn.dataset.pageUrl) {
                return;
            }

            if (btn.dataset.paginationBound === '1') {
                return;
            }

            btn.dataset.paginationBound = '1';
            btn.addEventListener('click', (event) => {
                event.preventDefault();
                const url = btn.dataset.pageUrl;
                if (!url) {
                    return;
                }
                this.fetchAndRenderResultados(url);
            });
        });
    }

    refreshDynamicElements() {
        this.formsEliminar = document.querySelectorAll('.form-eliminar');
        this.exportButtons = document.querySelectorAll('.export-btn');
        this.messageCloseButtons = document.querySelectorAll('.mensaje-cerrable .cerrar-mensaje');
        this.mensajesPrincipales = document.getElementById('mensajes-principales');
        this.btnLimpiarFiltros = this.formFiltros ? this.formFiltros.querySelector('#limpiar-filtros') : document.getElementById('limpiar-filtros');

        this.bindDeletionConfirmation();
        this.ensureExportBindings();
        this.bindMessageClosers();
        this.scrollToImportantMessage();
        this.bindAutoFilterControls();
        this.bindResetButton();
        this.bindModalEliminarStatics();
    }

    updateHistory(url) {
        if (!window.history || typeof window.history.replaceState !== 'function') {
            return;
        }
        try {
            const absolute = new URL(url, window.location.href);
            window.history.replaceState({}, '', absolute.pathname + absolute.search);
        } catch (error) {
            console.warn('No se pudo actualizar el historial:', error);
        }
    }

    aplicarFiltroAnioInicial() {
        try {
            const params = new URLSearchParams(window.location.search);
            if (!params.toString()) {
                const currentYear = new Date().getFullYear();
                const targetUrl = `${this.options.urlFiltroBase}?anio=${currentYear}`;
                window.location.replace(targetUrl);
            }
        } catch (error) {
            console.warn('No se pudo aplicar el filtro automático de año:', error);
        }
    }

    updateFechaHasta() {
        if (!this.inputFechaHasta) {
            return;
        }

        if (this.checkboxRango && this.checkboxRango.checked) {
            this.inputFechaHasta.style.display = '';
            this.inputFechaHasta.removeAttribute('disabled');
            this.inputFechaHasta.setAttribute('name', 'fecha_hasta');
        } else {
            this.inputFechaHasta.style.display = 'none';
            this.inputFechaHasta.setAttribute('disabled', 'disabled');
            this.inputFechaHasta.removeAttribute('name');
            this.inputFechaHasta.value = '';
        }
    }

    abrirModalRechazo(solicitudId) {
        if (!this.modalRechazo) return;
        this.modalRechazo.style.display = 'flex';
        if (this.inputSolicitudId) {
            this.inputSolicitudId.value = solicitudId;
        }
        if (this.textareaMotivo) {
            this.textareaMotivo.value = '';
            this.textareaMotivo.focus();
        }
    }

    abrirModalComentarios(solicitudId, comentario) {
        if (!this.modalComentarios || !this.contenidoComentarios) {
            return;
        }

        const texto = (comentario || '').trim();
        if (!texto || texto === 'None') {
            this.contenidoComentarios.innerHTML = '<p style="margin:0;color:#666;font-style:italic;font-size:14px;">No hay comentarios para esta solicitud.</p>';
        } else if (texto.includes(' - Motivo rechazo: ')) {
            const [comentarioEmpleado, motivoRechazo] = texto.split(' - Motivo rechazo: ');
            this.contenidoComentarios.innerHTML = `
                <div style="margin-bottom:12px;">
                    <strong style="color:#333;font-size:14px;">Comentario del empleado:</strong>
                    <p style="margin:4px 0 0 0;white-space:pre-wrap;font-size:14px;line-height:1.4;">${comentarioEmpleado.trim()}</p>
                </div>
                <div>
                    <strong style="color:#e74c3c;font-size:14px;">Motivo de rechazo:</strong>
                    <p style="margin:4px 0 0 0;white-space:pre-wrap;font-size:14px;line-height:1.4;font-weight:bold;">${motivoRechazo.trim()}</p>
                </div>`;
        } else {
            this.contenidoComentarios.innerHTML = `
                <div>
                    <strong style="color:#333;font-size:14px;">Comentario del empleado:</strong>
                    <p style="margin:4px 0 0 0;white-space:pre-wrap;font-size:14px;line-height:1.4;">${texto}</p>
                </div>`;
        }

        this.modalComentarios.style.display = 'flex';
    }

    cerrarModal(modal) {
        if (modal) {
            modal.style.display = 'none';
        }
    }

    confirmarRechazo() {
        if (!this.textareaMotivo || !this.inputSolicitudId) {
            return;
        }

        const motivo = this.textareaMotivo.value.trim();
        const solicitudId = this.inputSolicitudId.value;

        if (!motivo) {
            alert('Debes escribir el motivo del rechazo.');
            this.textareaMotivo.focus();
            return;
        }

        const selector = `form input[name="solicitud_id"][value="${solicitudId}"]`;
        const inputSolicitud = document.querySelector(selector);
        if (!inputSolicitud) {
            alert('No se encontró el formulario para esta solicitud.');
            this.cerrarModal(this.modalRechazo);
            return;
        }

        const form = inputSolicitud.closest('form');
        if (!form) {
            alert('No se encontró el formulario para esta solicitud.');
            this.cerrarModal(this.modalRechazo);
            return;
        }

        const motivoHidden = document.createElement('input');
        motivoHidden.type = 'hidden';
        motivoHidden.name = 'motivo_rechazo';
        motivoHidden.value = motivo;
        form.appendChild(motivoHidden);

        const accionHidden = document.createElement('input');
        accionHidden.type = 'hidden';
        accionHidden.name = 'accion';
        accionHidden.value = 'rechazar';
        form.appendChild(accionHidden);

        form.submit();
        this.cerrarModal(this.modalRechazo);
    }

    bindMessageClosers() {
        if (!this.messageCloseButtons || !this.messageCloseButtons.length) {
            return;
        }

        this.messageCloseButtons.forEach((btn) => {
            if (btn.dataset.msgCloserBound === '1') {
                return;
            }
            btn.dataset.msgCloserBound = '1';
            btn.addEventListener('click', () => {
                const parent = btn.closest('.mensaje-cerrable');
                if (parent) {
                    parent.style.display = 'none';
                }
            });
        });
    }

    scrollToImportantMessage() {
        if (!this.mensajesPrincipales) {
            return;
        }

        const mensajeError = this.mensajesPrincipales.querySelector('.mensaje-error');
        if (mensajeError) {
            this.mensajesPrincipales.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    bindDeletionConfirmation() {
        if (!this.formsEliminar || !this.formsEliminar.length) {
            return;
        }

        this.formsEliminar.forEach((form) => {
            if (form.dataset.confirmBound === '1') {
                return;
            }
            form.dataset.confirmBound = '1';
            form.addEventListener('submit', (event) => {
                if (!this.modalEliminar) {
                    const ok = window.confirm('¿Confirma que desea eliminar/cancelar esta solicitud? Esta acción no podrá deshacerse.');
                    if (!ok) {
                        event.preventDefault();
                    }
                    return;
                }

                event.preventDefault();
                this.formPendienteEliminar = form;
                this.toggleModalEliminar(true);
            });
        });
    }

    bindModalEliminarStatics() {
        if (this.modalEliminar && !this.modalEliminar.dataset.overlayBound) {
            this.modalEliminar.dataset.overlayBound = '1';
            this.modalEliminar.addEventListener('click', (event) => {
                if (event.target === this.modalEliminar) {
                    this.toggleModalEliminar(false);
                }
            });
        }

        if (this.btnCancelarEliminar && this.btnCancelarEliminar.dataset.bound !== '1') {
            this.btnCancelarEliminar.dataset.bound = '1';
            this.btnCancelarEliminar.addEventListener('click', () => {
                this.toggleModalEliminar(false);
                this.formPendienteEliminar = null;
            });
        }

        if (this.btnConfirmarEliminar && this.btnConfirmarEliminar.dataset.bound !== '1') {
            this.btnConfirmarEliminar.dataset.bound = '1';
            this.btnConfirmarEliminar.addEventListener('click', () => {
                if (this.formPendienteEliminar) {
                    const formToSubmit = this.formPendienteEliminar;
                    this.formPendienteEliminar = null;
                    this.toggleModalEliminar(false);
                    formToSubmit.submit();
                } else {
                    this.toggleModalEliminar(false);
                }
            });
        }
    }

    toggleModalEliminar(show) {
        if (!this.modalEliminar) {
            return;
        }
        this.modalEliminar.setAttribute('aria-hidden', show ? 'false' : 'true');
        this.modalEliminar.classList.toggle('visible', !!show);
        document.body.classList.toggle('modal-open', !!show);
    }

    ensureExportBindings() {
        if (!this.exportButtons || !this.exportButtons.length) {
            return;
        }

        try {
            if (window.exportUtils && typeof window.exportUtils.bindExportButtons === 'function') {
                window.exportUtils.bindExportButtons(document);
            }
        } catch (error) {
            console.warn('Failed to bind export buttons:', error);
        }
    }
}

window.GestionReporteLicencias = GestionReporteLicencias;
