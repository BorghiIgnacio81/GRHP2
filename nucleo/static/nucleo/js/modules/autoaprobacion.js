/**
 * Módulo simple para validación de autoaprobación
 * Intercepta formularios y valida antes de enviar
 */

class AutoaprobacionValidator {
    constructor() {
        this.init();
    }
    
    init() {
        console.log('🔒 Inicializando validador de autoaprobación...');
        this.interceptarFormularios();
    }
    
    /**
     * Interceptar todos los formularios con botones de aprobación
     */
    interceptarFormularios() {
        const formularios = document.querySelectorAll('form');
        
        formularios.forEach(form => {
            const botonAprobar = form.querySelector('button[value="aprobar"]');
            if (botonAprobar) {
                console.log('🎯 Formulario de aprobación encontrado');
                form.addEventListener('submit', (e) => this.validarFormulario(e));
            }
        });
    }
    
    /**
     * Validar formulario - ahora solo muestra mensaje informativo
     * La validación real la hace el servidor Django
     */
    validarFormulario(event) {
        const form = event.target;
        const botonPresionado = event.submitter;
        
        if (botonPresionado && botonPresionado.value === 'aprobar') {
            console.log('🔍 Procesando aprobación...');
            
            // Mostrar mensaje informativo (no bloquear)
            if (window.Mensajes) {
                window.Mensajes.mostrarAdvertencia('⏳ Procesando aprobación...');
            }
            
            // Dejar que el servidor maneje la validación real
            return true;
        }
        
        return true;
    }
    
    /**
     * Obtener ID del usuario actual desde meta tag
     */
    obtenerUsuarioActual() {
        const meta = document.querySelector('meta[name="user-id"]');
        return meta ? meta.content : null;
    }
    
    // Métodos auxiliares simplificados (no usados en la validación actual)
    
    /**
     * Mostrar mensaje de bloqueo
     */
    mostrarBloqueo() {
        const mensaje = "❌ No puedes aprobar tus propias solicitudes. Debe hacerlo otro gestor.";
        
        // Usar el sistema de mensajes global si está disponible
        if (window.Mensajes) {
            window.Mensajes.mostrarError(mensaje);
        } else {
            // Fallback: alerta simple
            alert(mensaje);
        }
        
        console.log('🚫 Autoaprobación bloqueada');
    }
}

// Inicializar cuando esté listo
let autoaprobacionValidator;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        autoaprobacionValidator = new AutoaprobacionValidator();
    });
} else {
    autoaprobacionValidator = new AutoaprobacionValidator();
}

// Exponer globalmente
window.AutoaprobacionValidator = autoaprobacionValidator;