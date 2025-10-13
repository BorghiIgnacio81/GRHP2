/**
 * PROTOCOLO1 MODULARIZADO: Gestión de auditoría y filtros de fecha
 * Funcionalidad: Toggle de rango de fechas, navegación con parámetros, limpieza de URL
 * Created: 2025-01-11
 */

class LogAuditoriaModule {
    constructor(config = {}) {
        this.config = {
            rangoFechaCheckbox: config.rangoFechaCheckbox || '#audit_rango_fecha',
            fechaHastaInput: config.fechaHastaInput || '#audit_fecha_hasta',
            cleanUrlOnReload: config.cleanUrlOnReload !== false,
            ...config
        };
        this.init();
    }

    init() {
        this.setupToggleRangoFecha();
        if (this.config.cleanUrlOnReload) {
            this.setupUrlCleaner();
        }
    }

    setupToggleRangoFecha() {
        const checkbox = document.querySelector(this.config.rangoFechaCheckbox);
        if (checkbox) {
            checkbox.addEventListener('change', () => this.toggleRangoFecha());
            this.toggleRangoFecha();
        }
    }

    toggleRangoFecha() {
        const checkbox = document.querySelector(this.config.rangoFechaCheckbox);
        const fechaHasta = document.querySelector(this.config.fechaHastaInput);
        if (!fechaHasta) return;

        try {
            if (checkbox && checkbox.checked) {
                fechaHasta.style.display = '';
                fechaHasta.disabled = false;
                fechaHasta.setAttribute('name', 'fecha_hasta');
                setTimeout(() => {
                    try {
                        fechaHasta.focus();
                    } catch (e) {
                        console.warn('No se pudo enfocar fecha_hasta:', e);
                    }
                }, 100);
            } else {
                fechaHasta.style.display = 'none';
                fechaHasta.disabled = true;
                try {
                    fechaHasta.value = '';
                    fechaHasta.removeAttribute('name');
                } catch (e) {
                    console.warn('Error al limpiar fecha_hasta:', e);
                }
            }
        } catch (e) {
            console.error('Error en toggleRangoFecha:', e);
        }
    }

    setupUrlCleaner() {
        try {
            const params = new URLSearchParams(window.location.search);
            const hasLogParams = params.has('log_order') || params.has('log_dir');
            if (!hasLogParams) return;

            const reloaded = this.isPageReloaded();
            if (hasLogParams && reloaded) {
                console.log('🔄 Limpiando parámetros de ordenamiento en recarga');
                params.delete('log_order');
                params.delete('log_dir');
                const newQuery = params.toString();
                const newUrl = window.location.pathname + (newQuery ? ('?' + newQuery) : '');
                history.replaceState(null, '', newUrl);
                window.location.replace(newUrl);
            }
        } catch (e) {
            console.warn('Limpiador de URL falló (no crítico):', e);
        }
    }

    isPageReloaded() {
        try {
            if (performance && typeof performance.getEntriesByType === 'function') {
                const navigationEntries = performance.getEntriesByType('navigation');
                if (navigationEntries.length > 0) {
                    return navigationEntries[0].type === 'reload';
                }
            }
            if (performance && performance.navigation) {
                return performance.navigation.type === 1;
            }
            return false;
        } catch (e) {
            console.warn('No se pudo detectar recarga de página:', e);
            return false;
        }
    }

    aplicarFiltros(filtros = {}) {
        const form = document.querySelector('form');
        if (!form) return false;
        Object.keys(filtros).forEach(campo => {
            const input = form.querySelector(`[name="${campo}"]`);
            if (input) {
                input.value = filtros[campo];
            }
        });
        form.submit();
        return true;
    }

    getFiltrosActuales() {
        const params = new URLSearchParams(window.location.search);
        const filtros = {};
        const camposFiltro = ['tabla', 'fecha_desde', 'fecha_hasta', 'usuario', 'accion'];
        camposFiltro.forEach(campo => {
            if (params.has(campo)) {
                filtros[campo] = params.get(campo);
            }
        });
        return filtros;
    }

    limpiarFiltros() {
        const form = document.querySelector('form');
        if (!form) return false;
        form.reset();
        const checkbox = document.querySelector(this.config.rangoFechaCheckbox);
        if (checkbox) {
            checkbox.checked = false;
            this.toggleRangoFecha();
        }
        return true;
    }
}

window.LogAuditoriaModule = LogAuditoriaModule;
