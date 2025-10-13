/**
 * Módulo universal para manejo de mensajes en todas las páginas
 * Funciona sin dependencias externas y sin localStorage
 */

class MensajesManager {
    constructor() {
        this.init();
    }
    
    init() {
        console.log('📢 Inicializando sistema de mensajes...');
        this.configurarCerrarMensajes();
    }
    
    /**
     * Configurar botones X para cerrar mensajes
     */
    configurarCerrarMensajes() {
        const botonesCerrar = document.querySelectorAll('.cerrar-mensaje');
        botonesCerrar.forEach(btn => {
            btn.addEventListener('click', () => {
                const mensaje = btn.parentElement;
                mensaje.style.animation = 'fadeOut 0.3s';
                setTimeout(() => {
                    mensaje.style.display = 'none';
                }, 300);
            });
        });
    }
    
    /**
     * Mostrar mensaje de éxito
     */
    mostrarExito(texto) {
        this.mostrarMensaje(texto, 'exito');
    }
    
    /**
     * Mostrar mensaje de error
     */
    mostrarError(texto) {
        this.mostrarMensaje(texto, 'error');
    }
    
    /**
     * Mostrar mensaje de advertencia
     */
    mostrarAdvertencia(texto) {
        this.mostrarMensaje(texto, 'advertencia');
    }
    
    /**
     * Crear y mostrar mensaje dinámico
     */
    mostrarMensaje(texto, tipo = 'exito') {
        const container = this.obtenerContainer();
        const clase = tipo === 'error' ? 'mensaje-error' : 'mensaje-exito';
        
        const mensaje = document.createElement('div');
        mensaje.className = `${clase} mensaje-cerrable mensaje-dinamico`;
        mensaje.innerHTML = `
            <span class="cerrar-mensaje" style="float:right;cursor:pointer;font-weight:bold;font-size:1.2em;margin-left:10px;">&times;</span>
            ${texto}
        `;
        
        container.appendChild(mensaje);
        
        // Configurar cierre para el nuevo mensaje
        const btnCerrar = mensaje.querySelector('.cerrar-mensaje');
        btnCerrar.addEventListener('click', () => {
            mensaje.style.animation = 'fadeOut 0.3s';
            setTimeout(() => mensaje.remove(), 300);
        });
        
        // Auto-eliminar después de 8 segundos (solo mensajes dinámicos)
        setTimeout(() => {
            if (mensaje.parentElement) {
                mensaje.style.animation = 'fadeOut 0.3s';
                setTimeout(() => mensaje.remove(), 300);
            }
        }, 8000);
        
        return mensaje;
    }
    
    /**
     * Obtener o crear contenedor de mensajes
     */
    obtenerContainer() {
        let container = document.getElementById('mensajes-dinamicos-container');
        
        if (!container) {
            container = document.createElement('div');
            container.id = 'mensajes-dinamicos-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                max-width: 400px;
                pointer-events: none;
            `;
            
            // Los mensajes en sí tendrán pointer-events: auto
            container.addEventListener('click', (e) => {
                e.target.style.pointerEvents = 'auto';
            });
            
            document.body.appendChild(container);
        }
        
        return container;
    }
    
    /**
     * Limpiar todos los mensajes dinámicos
     */
    limpiarMensajes() {
        const mensajesDinamicos = document.querySelectorAll('.mensaje-dinamico');
        mensajesDinamicos.forEach(msg => {
            msg.style.animation = 'fadeOut 0.3s';
            setTimeout(() => msg.remove(), 300);
        });
    }
}

// Agregar estilos para animaciones
const estilos = document.createElement('style');
estilos.textContent = `
    @keyframes fadeOut {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(100px); }
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateX(100px); }
        to { opacity: 1; transform: translateX(0); }
    }
    
    .mensaje-dinamico {
        animation: slideIn 0.3s ease-out;
        margin-bottom: 10px;
        pointer-events: auto;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border-radius: 6px;
        max-width: 100%;
        word-wrap: break-word;
    }
`;
document.head.appendChild(estilos);

// Inicializar cuando esté listo
let mensajesManager;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        mensajesManager = new MensajesManager();
    });
} else {
    mensajesManager = new MensajesManager();
}

// Exponer globalmente para uso en cualquier página
window.Mensajes = mensajesManager;