/**
 * Coordinador principal para la pantalla de modificar/borrar empleado.
 * Encapsula todas las interacciones de la página para evitar scripts inline.
 */
class ModificarEmpleadoMaestro {
    constructor() {
        this.inicializado = false;
        this.componentes = {};
        this.elementos = {};
    }

    init() {
        if (this.inicializado) {
            console.warn('ModificarEmpleadoMaestro ya inicializado');
            return;
        }

        this.cachearElementos();
        this.initFormularioControl();
        this.initMascaraDNI();
        this.initCalculoCUIL();
        this.initComboLocalidad();
        this.initBuscadorEmpleados();
        this.initDeteccionCambios();
        this.initModalBorrar();

        this.inicializado = true;
    }

    cachearElementos() {
        this.elementos = {
            form: document.getElementById('form-actualizar'),
            busquedaEmpleado: document.getElementById('busqueda-empleado'),
            resultadosAutocomplete: document.getElementById('resultados-autocomplete'),
            dniInput: document.getElementById('id_dni'),
            cuilInput: document.getElementById('id_cuil'),
            sexoInput: document.getElementById('id_sexo') || document.querySelector('select[name="id_sexo"]'),
            inputLocalidad: document.getElementById('input_localidad'),
            hiddenIdLocalidad: document.getElementById('id_localidad'),
            provinciaSelect: document.getElementById('provincia'),
            dropdownLocalidad: document.getElementById('dropdown_localidad'),
            btnActualizar: document.querySelector('.btn-actualizar'),
            modalBorrar: document.getElementById('modal-borrar')
        };
    }

    initFormularioControl() {
        if (!this.elementos.form) return;
        const empleadoCargado = this.elementos.form.hasAttribute('data-empleado-cargado');
        if (!empleadoCargado) {
            const campos = Array.from(this.elementos.form.elements).filter(el =>
                ['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) &&
                el.type !== 'hidden' &&
                el.id !== 'busqueda-empleado'
            );
            campos.forEach(el => { el.disabled = true; });
        }
    }

    initMascaraDNI() {
        if (!this.elementos.dniInput) return;

        const aplicarMascara = (valor) => {
            const value = String(valor).replace(/\D/g, '').substring(0, 8);
            if (value.length > 5) {
                return `${value.substring(0, 2)}.${value.substring(2, 5)}.${value.substring(5)}`;
            }
            if (value.length > 2) {
                return `${value.substring(0, 2)}.${value.substring(2)}`;
            }
            return value;
        };

        this.elementos.dniInput.value = aplicarMascara(this.elementos.dniInput.value);

        this.elementos.dniInput.addEventListener('input', (event) => {
            event.target.value = aplicarMascara(event.target.value);
        });
    }

    initCalculoCUIL() {
        if (!this.elementos.dniInput || !this.elementos.sexoInput || !this.elementos.cuilInput) return;

        const calcularCuil = () => {
            const dni = this.elementos.dniInput.value.replace(/\D/g, '');
            const sexo = this.elementos.sexoInput.value;

            if (dni.length !== 8 || !sexo) {
                this.elementos.cuilInput.value = '';
                return;
            }

            let prefijo = 20;
            if (sexo === '2') prefijo = 27;
            if (sexo !== '1' && sexo !== '2') prefijo = 23;

            const dniStr = dni.padStart(8, '0');
            const base = `${prefijo}${dniStr}`;
            const pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
            let suma = 0;
            for (let i = 0; i < 10; i++) {
                suma += parseInt(base[i], 10) * pesos[i];
            }
            let resto = suma % 11;
            let verificador = 11 - resto;
            if (verificador === 11) verificador = 0;
            else if (verificador === 10) {
                prefijo = 23;
                const nuevoBase = `${prefijo}${dniStr}`;
                suma = 0;
                for (let i = 0; i < 10; i++) {
                    suma += parseInt(nuevoBase[i], 10) * pesos[i];
                }
                resto = suma % 11;
                verificador = 11 - resto;
                if (verificador === 11) verificador = 0;
            }

            const dniMask = `${dniStr.substring(0, 2)}.${dniStr.substring(2, 5)}.${dniStr.substring(5)}`;
            this.elementos.cuilInput.value = `${prefijo}-${dniMask}-${verificador}`;
        };

        this.elementos.cuilInput.readOnly = true;
        this.elementos.cuilInput.style.background = '#f2f2f7';
        this.elementos.cuilInput.tabIndex = -1;

        this.elementos.dniInput.addEventListener('blur', calcularCuil);
        this.elementos.dniInput.addEventListener('change', calcularCuil);
        this.elementos.sexoInput.addEventListener('change', calcularCuil);

        setTimeout(calcularCuil, 100);
    }

    initComboLocalidad() {
        if (!this.elementos.inputLocalidad || !this.elementos.provinciaSelect) return;

        let timeout = null;
        let resultados = [];
        let valorOriginal = this.elementos.inputLocalidad.value;
        let idOriginal = this.elementos.hiddenIdLocalidad.value;
        const limpiarDropdown = () => {
            if (!this.elementos.dropdownLocalidad) return;
            this.elementos.dropdownLocalidad.innerHTML = '';
            this.elementos.dropdownLocalidad.style.display = 'none';
        };

        const mostrarDropdown = (items) => {
            if (!this.elementos.dropdownLocalidad) return;

            if (!items.length) {
                this.elementos.dropdownLocalidad.innerHTML = '<div class="autocomplete-noresult">Sin resultados</div>';
            } else {
                this.elementos.dropdownLocalidad.innerHTML = items.map((item, index) => `
                    <div class="autocomplete-item" data-id="${item.id}" data-index="${index}">${item.localidad}</div>
                `).join('');

                this.elementos.dropdownLocalidad.querySelectorAll('.autocomplete-item').forEach(div => {
                    div.addEventListener('mousedown', () => {
                        this.elementos.inputLocalidad.value = div.textContent;
                        this.elementos.hiddenIdLocalidad.value = div.dataset.id;
                        limpiarDropdown();
                    });
                });
            }

            this.elementos.dropdownLocalidad.style.display = 'block';
        };

        const buscar = async (texto) => {
            if (!texto || texto.length < 2 || !this.elementos.provinciaSelect.value) {
                limpiarDropdown();
                return;
            }

            try {
                const url = `/ajax/localidades/?provincia_id=${this.elementos.provinciaSelect.value}&q=${encodeURIComponent(texto)}`;
                const response = await fetch(url);
                resultados = await response.json();
                mostrarDropdown(resultados);
            } catch (error) {
                console.error('Error consultando localidades', error);
                limpiarDropdown();
            }
        };

        this.elementos.inputLocalidad.addEventListener('focus', () => {
            valorOriginal = this.elementos.inputLocalidad.value;
            idOriginal = this.elementos.hiddenIdLocalidad.value;
        });

        this.elementos.inputLocalidad.addEventListener('input', (event) => {
            const texto = event.target.value.trim();
            this.elementos.hiddenIdLocalidad.value = '';

            if (timeout) clearTimeout(timeout);
            timeout = setTimeout(() => buscar(texto), 200);
        });

        this.elementos.inputLocalidad.addEventListener('blur', () => {
            setTimeout(() => {
                if (this.elementos.dropdownLocalidad && this.elementos.dropdownLocalidad.contains(document.activeElement)) {
                    return;
                }

                const val = this.elementos.inputLocalidad.value.trim();
                if (!val) {
                    this.elementos.hiddenIdLocalidad.value = '';
                    limpiarDropdown();
                    return;
                }

                const match = resultados.find(loc => loc.localidad.toLowerCase() === val.toLowerCase());
                if (match) {
                    this.elementos.hiddenIdLocalidad.value = match.id;
                    limpiarDropdown();
                    return;
                }

                this.mostrarModalCrearLocalidad(val, valorOriginal, idOriginal);
            }, 200);
        });

        this.elementos.provinciaSelect.addEventListener('change', () => {
            this.elementos.inputLocalidad.value = '';
            this.elementos.hiddenIdLocalidad.value = '';
            limpiarDropdown();
        });

        document.addEventListener('mousedown', (event) => {
            if (!this.elementos.dropdownLocalidad) return;
            if (!this.elementos.dropdownLocalidad.contains(event.target) && event.target !== this.elementos.inputLocalidad) {
                limpiarDropdown();
            }
        });

        if (this.elementos.form) {
            this.elementos.form.addEventListener('submit', (e) => {
                if (!this.elementos.hiddenIdLocalidad.value || isNaN(Number(this.elementos.hiddenIdLocalidad.value))) {
                    e.preventDefault();
                    this.mostrarModalCrearLocalidad(this.elementos.inputLocalidad.value.trim(), valorOriginal, idOriginal);
                }
            });
        }
    }

    mostrarModalCrearLocalidad(nombre, valorOriginal = '', idOriginal = '') {
        if (!nombre) return;

        let modal = document.getElementById('modal-crear-localidad');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'modal-crear-localidad';
            modal.style.position = 'fixed';
            modal.style.top = '0';
            modal.style.left = '0';
            modal.style.width = '100vw';
            modal.style.height = '100vh';
            modal.style.background = 'rgba(0,0,0,0.3)';
            modal.style.display = 'flex';
            modal.style.alignItems = 'center';
            modal.style.justifyContent = 'center';
            modal.innerHTML = `
                <div style="background:#fff; border-radius:10px; padding:32px 28px; max-width:400px; margin:auto; box-shadow:0 2px 12px #0003; text-align:center;">
                    <div class="mensaje-modal-localidad" style="margin-bottom:18px;"></div>
                    <button type="button" class="btn-confirmar-verde" data-modal-si style="margin-right:12px;">Sí</button>
                    <button type="button" class="btn-borrar" data-modal-no>No</button>
                </div>`;
            document.body.appendChild(modal);
        }

        const mensaje = modal.querySelector('.mensaje-modal-localidad');
        if (mensaje) {
            let provinciaNombre = '';
            if (this.elementos.provinciaSelect) {
                const opt = this.elementos.provinciaSelect.options[this.elementos.provinciaSelect.selectedIndex];
                provinciaNombre = opt ? opt.text : '';
            }
            mensaje.innerHTML = `La localidad <b>${nombre}</b> no existe en la provincia <b>${provinciaNombre}</b>. ¿Desea crearla?`;
        }

        const btnSi = modal.querySelector('[data-modal-si]');
        const btnNo = modal.querySelector('[data-modal-no]');

        btnSi.onclick = () => {
            this.crearLocalidad(nombre).finally(() => {
                modal.style.display = 'none';
            });
        };

        btnNo.onclick = () => {
            modal.style.display = 'none';
            this.elementos.inputLocalidad.value = valorOriginal || '';
            this.elementos.hiddenIdLocalidad.value = idOriginal || '';
        };

        modal.style.display = 'flex';
    }

    async crearLocalidad(nombre) {
        try {
            const response = await fetch('/ajax/crear_localidad/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.obtenerCsrfToken()
                },
                body: JSON.stringify({
                    provincia_id: this.elementos.provinciaSelect.value,
                    localidad: nombre
                })
            });

            const data = await response.json();
            if (data && data.id) {
                this.elementos.inputLocalidad.value = nombre;
                this.elementos.hiddenIdLocalidad.value = data.id;
            }
        } catch (error) {
            console.error('Error creando localidad', error);
        }
    }

    initBuscadorEmpleados() {
        if (!this.elementos.busquedaEmpleado || !this.elementos.resultadosAutocomplete) return;

        if (typeof BuscadorEmpleados === 'undefined') {
            console.warn('BuscadorEmpleados no está disponible');
            return;
        }

        const urlBusqueda = window.urlBuscarEmpleados || '/nucleo/empleados/buscar_ajax/';

        this.componentes.buscador = new BuscadorEmpleados({
            inputSelector: '#busqueda-empleado',
            resultsSelector: '#resultados-autocomplete',
            urlBusqueda,
            onSelect: (empleado) => {
                window.location.href = `/nucleo/empleados/modificar/${empleado.id}/`;
            },
            placeholder: 'Buscar por ID, Apellido o Nombre',
            minCharacters: 1,
            delay: 200,
            soloEstadoActual: true
        });
    }

    initDeteccionCambios() {
        if (!this.elementos.form || !this.elementos.btnActualizar) return;

        const campos = Array.from(this.elementos.form.elements).filter(el =>
            ['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) &&
            el.type !== 'hidden' &&
            el.name
        );

        const valoresOriginales = campos.map(el =>
            el.type === 'checkbox' ? el.checked : el.value
        );

        const normalizar = (el, valor) => {
            const nombre = (el.name || '').toLowerCase();
            if (nombre.includes('dni') || nombre.includes('cuil')) {
                return String(valor || '').replace(/\D/g, '');
            }
            return el.type === 'checkbox' ? Boolean(valor) : String(valor ?? '');
        };

        const actualizarEstado = () => {
            const hayCambios = campos.some((el, index) => {
                const actual = el.type === 'checkbox' ? el.checked : el.value;
                return normalizar(el, actual) !== normalizar(el, valoresOriginales[index]);
            });

            this.elementos.btnActualizar.disabled = !hayCambios;
            this.elementos.btnActualizar.classList.toggle('completo', hayCambios);
        };

        campos.forEach(el => {
            el.addEventListener('input', actualizarEstado);
            el.addEventListener('change', actualizarEstado);
        });

        actualizarEstado();
    }

    initModalBorrar() {
        window.abrirModalBorrar = () => {
            if (this.elementos.modalBorrar) {
                this.elementos.modalBorrar.style.display = 'flex';
            }
        };

        window.cerrarModalBorrar = () => {
            if (this.elementos.modalBorrar) {
                this.elementos.modalBorrar.style.display = 'none';
            }
        };
    }

    obtenerCsrfToken() {
        const match = document.cookie.split(';').find(cookie => cookie.trim().startsWith('csrftoken='));
        if (!match) return '';
        return decodeURIComponent(match.split('=')[1]);
    }
}

window.ModificarEmpleadoMaestro = ModificarEmpleadoMaestro;
