// JS para reforzar CSRF en AJAX y restaurar diseño y funcionalidad
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function csrfSafeMethod(method) {
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

// Interceptar todos los fetch para agregar CSRF
(function() {
    const _fetch = window.fetch;
    window.fetch = function(input, init) {
        init = init || {};
        init.headers = init.headers || {};
        if (!csrfSafeMethod(init.method || 'GET')) {
            const csrftoken = getCookie('csrftoken');
            if (csrftoken) {
                init.headers['X-CSRFToken'] = csrftoken;
            }
        }
        return _fetch(input, init);
    };
})();

// Refuerzo: normalización y comparación estricta para DNI/CUIL
function normNum(val) {
    return String(val || '').replace(/\D/g, '');
}
function minimalChanged(orig, actual) {
    return normNum(orig) !== normNum(actual);
}
// Refuerzo visual y cálculo automático de CUIL
function calcularCuil(dni, sexo) {
    let prefijo = 20;
    if (sexo == '2') prefijo = 27;
    if (sexo != '1' && sexo != '2') prefijo = 23;
    let dni_str = String(dni).replace(/\D/g, '').padStart(8, '0');
    let base = String(prefijo) + dni_str;
    let pesos = [5,4,3,2,7,6,5,4,3,2];
    let suma = 0;
    for (let i = 0; i < 10; i++) suma += parseInt(base[i]) * pesos[i];
    let resto = suma % 11;
    let verificador = 11 - resto;
    if (verificador === 11) verificador = 0;
    else if (verificador === 10) {
        prefijo = 23;
        base = String(prefijo) + dni_str;
        suma = 0;
        for (let i = 0; i < 10; i++) suma += parseInt(base[i]) * pesos[i];
        resto = suma % 11;
        verificador = 11 - resto;
        if (verificador === 11) verificador = 0;
    }
    let dni_masked = dni_str.substring(0,2) + '.' + dni_str.substring(2,5) + '.' + dni_str.substring(5);
    return `${prefijo}-${dni_masked}-${verificador}`;
}
document.addEventListener('DOMContentLoaded', function() {
    console.log('JS reforzado cargado correctamente');

    // Activar/desactivar campos según si hay empleado
    var empleadoCargado = document.getElementById('form-actualizar') ? true : false;
    if (!empleadoCargado) {
        var form = document.getElementById('form-actualizar');
        if (form) {
            var campos = Array.from(form.elements).filter(function(el) {
                return ['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) && el.type !== 'hidden' && el.id !== 'busqueda-empleado';
            });
            campos.forEach(function(el) { el.disabled = true; });
        }
    }

    // Máscara DNI mejorada
    var dniInput = document.getElementById('id_dni');
    if (dniInput) {
        // Aplicar máscara inicial
        let initialValue = dniInput.value.replace(/\D/g, '').substring(0, 8);
        let formatted = '';
        if (initialValue.length > 5) {
            formatted = initialValue.substring(0, 2) + '.' + initialValue.substring(2, 5) + '.' + initialValue.substring(5);
        } else if (initialValue.length > 2) {
            formatted = initialValue.substring(0, 2) + '.' + initialValue.substring(2);
        } else {
            formatted = initialValue;
        }
        dniInput.value = formatted;

        dniInput.addEventListener('input', function(e) {
            let value = this.value.replace(/\D/g, '').substring(0, 8);
            let formatted = '';
            if (value.length > 5) {
                formatted = value.substring(0, 2) + '.' + value.substring(2, 5) + '.' + value.substring(5);
            } else if (value.length > 2) {
                formatted = value.substring(0, 2) + '.' + value.substring(2);
            } else {
                formatted = value;
            }
            this.value = formatted;
        });
    }

    // Refuerzo visual DNI/CUIL
    const cuilInput = document.getElementById('id_cuil');
    const sexoInput = document.getElementById('id_sexo');
    if (dniInput && sexoInput && cuilInput) {
        dniInput.addEventListener('blur', function() {
            cuilInput.value = calcularCuil(dniInput.value, sexoInput.value);
        });
        sexoInput.addEventListener('change', function() {
            cuilInput.value = calcularCuil(dniInput.value, sexoInput.value);
        });
    }

    // Activar botón solo si hay cambios REALES
    const form = document.getElementById('form-actualizar');
    if (form) {
        const btn = form.querySelector('.btn-actualizar');
        if (btn) {
            const campos = Array.from(form.elements).filter(el =>
                ['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) && el.type !== 'hidden' && el.name
            );

            // Normalizar valores para comparación: quitar caracteres no numéricos en DNI/CUIL
            function normalizarValor(el, val) {
                if (!el || !el.name) return val;
                const name = el.name.toLowerCase();
                if (name.includes('dni') || name.includes('cuil')) {
                    return String(val || '').replace(/\D/g, '');
                }
                if (el.type === 'checkbox') return el.checked;
                return val === null || val === undefined ? '' : String(val);
            }

            const valoresOriginales = campos.map(el => normalizarValor(el, el.type === 'checkbox' ? el.checked : el.value));

            function checkCambios() {
                const cambios = [];
                campos.forEach((el, i) => {
                    const actual = normalizarValor(el, el.type === 'checkbox' ? el.checked : el.value);
                    if (actual != valoresOriginales[i]) {
                        cambios.push(`${el.name}: '${valoresOriginales[i]}' -> '${actual}'`);
                    }
                });

                const hayCambiosReales = cambios.length > 0;
                btn.disabled = !hayCambiosReales;
                btn.classList.toggle('completo', hayCambiosReales);

                console.log('Cambios detectados:', cambios);
                console.log('Botón disabled:', btn.disabled);

                return cambios;
            }

            campos.forEach(el => {
                el.addEventListener('input', checkCambios);
                el.addEventListener('change', checkCambios);
            });

            // Ejecutar check inicial
            checkCambios();
        }
    }

    // Verificar estado inicial del campo localidad
    const idLocalidadField = document.getElementById('id_localidad');
    if (idLocalidadField) {
        console.log('Campo id_localidad encontrado, valor inicial:', idLocalidadField.value);
    }

    // Mejorar el manejo del envío del formulario
    if (form) {
        form.addEventListener('submit', function(e) {
            console.log('Formulario enviado, verificando cambios...');
            // La lógica de cambios ya se maneja en checkCambios()
            console.log('Formulario se enviará normalmente');
        });
    }

    // Arreglar modal de confirmación
    const modal = document.getElementById('modal-actualizar');
    if (modal) {
        console.log('Modal de actualizar encontrado');

        // Buscar el formulario dentro del modal
        const formConfirm = modal.querySelector('form');
        if (formConfirm) {
            console.log('Formulario de confirmación encontrado');

            // Manejar los botones del modal
            const btnSi = formConfirm.querySelector('button[name="confirmar"][value="si"]');
            const btnNo = formConfirm.querySelector('button[name="confirmar"][value="no"]');

            if (btnSi) {
                btnSi.addEventListener('click', function(e) {
                    console.log('Botón Sí presionado, enviando formulario...');
                    // El formulario se enviará automáticamente, no necesitamos prevenir el default
                    // Solo aseguramos que el modal se cierre después del envío
                    setTimeout(() => {
                        modal.style.display = 'none';
                    }, 100);
                });
            }

            if (btnNo) {
                btnNo.addEventListener('click', function(e) {
                    console.log('Botón No presionado, cerrando modal...');
                    modal.style.display = 'none';
                    // Prevenir el envío del formulario
                    e.preventDefault();
                });
            }
        }
    }

    // Manejar modal de borrado
    const modalBorrar = document.getElementById('modal-borrar');
    if (modalBorrar) {
        console.log('Modal de borrado encontrado');

        const formBorrar = modalBorrar.querySelector('form');
        if (formBorrar) {
            const btnNoBorrar = formBorrar.querySelector('button[name="confirmar"][value="no"]');

            if (btnNoBorrar) {
                btnNoBorrar.addEventListener('click', function(e) {
                    console.log('Botón No del modal de borrado presionado, cerrando modal...');
                    modalBorrar.style.display = 'none';
                    e.preventDefault();
                });
            }
        }
    }
});
