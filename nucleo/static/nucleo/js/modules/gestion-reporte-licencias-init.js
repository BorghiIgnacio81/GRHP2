/**
 * Inicializador dedicado para la pantalla de Gestión / Reporte de Licencias.
 * Obtiene la configuración embebida en el DOM y crea la instancia del controlador principal.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (typeof window.GestionReporteLicencias !== 'function') {
        console.warn('GestionReporteLicencias no está disponible en la ventana global.');
        return;
    }

    const container = document.querySelector('[data-gestion-licencias]');
    const options = {};

    if (container) {
        const urlBase = container.getAttribute('data-url-base');
        const autoFilterAttr = container.getAttribute('data-auto-filter-year');

        if (urlBase) {
            options.urlFiltroBase = urlBase;
        }

        if (autoFilterAttr !== null) {
            options.autoFilterYear = autoFilterAttr !== 'false';
        }
    }

    window.gestionReporteLicencias = new window.GestionReporteLicencias(options);
});
