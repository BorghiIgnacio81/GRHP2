// Combo Localidad Editable reutilizable para alta y modificar empleado
// Requiere: select con id 'id_localidad', input con id 'input_localidad_nueva', botón con id 'btn-guardar-localidad', tooltip con id 'localidad-tooltip', select provincia con id 'provincia'
// El tooltip solo aparece al hacer hover sobre el select y solo si está habilitado

(function(){
    // Inyectar CSS del tooltip si no existe
    if (!document.getElementById('combo-localidad-tooltip-style')) {
        const style = document.createElement('style');
        style.id = 'combo-localidad-tooltip-style';
        style.innerHTML = `
#localidad-tooltip {
    display: none;
    position: absolute;
    left: 0;
    top: 100%;
    margin-top: 4px;
    background: #222;
    color: #fff;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 13px;
    z-index: 100;
    white-space: nowrap;
    min-width: 220px;
    box-shadow: 0 2px 8px #0002;
}
.localidad-select-tooltip { position: relative; display: inline-block; width: 100%; }
`;
        document.head.appendChild(style);
    }
})();

function initComboLocalidadEditable() {
    const localidadSelect = document.getElementById('id_localidad');
    const localidadInput = document.getElementById('input_localidad_nueva');
    const btnGuardarLocalidad = document.getElementById('btn-guardar-localidad');
    const tooltip = document.getElementById('localidad-tooltip');
    const provinciaSelect = document.getElementById('provincia');
    if (!localidadSelect || !localidadInput || !btnGuardarLocalidad || !tooltip || !provinciaSelect) return;
    // funcionalidad adicional para el combo editable puede ir aquí si se requiere
}

// Combo Localidad Autocomplete reutilizable
// Requiere: input con id 'input_localidad', select provincia con id 'provincia'
// El input debe tener name='localidad' y el id del campo hidden para el id de localidad debe ser 'id_localidad' (type=hidden)

function initComboLocalidadAutocomplete({
    inputId = 'input_localidad',
    provinciaId = 'provincia',
    hiddenId = 'id_localidad',
    endpointBuscar = '/ajax/localidades/',
    endpointCrear = '/ajax/crear_localidad/',
    minLength = 2
} = {}) {
    const input = document.getElementById(inputId);
    const provincia = document.getElementById(provinciaId);
    const hidden = document.getElementById(hiddenId);
    if (!input || !provincia || !hidden) return;

    // Crear dropdown
    let dropdown = document.createElement('div');
    dropdown.className = 'autocomplete-dropdown';
    dropdown.style.position = 'absolute';
    dropdown.style.zIndex = 1000;
    dropdown.style.background = '#fff';
    dropdown.style.border = '1px solid #ccc';
    dropdown.style.width = input.offsetWidth + 'px';
    dropdown.style.maxHeight = '180px';
    dropdown.style.overflowY = 'auto';
    dropdown.style.display = 'none';
    input.parentElement.appendChild(dropdown);

    let localidades = [];
    let selectedId = null;

    function closeDropdown() { dropdown.style.display = 'none'; }
    function openDropdown() { dropdown.style.display = 'block'; dropdown.style.width = input.offsetWidth + 'px'; }

    function renderDropdown(items) {
        if (!items.length) {
            dropdown.innerHTML = '<div class="autocomplete-noresult">Sin resultados</div>';
        } else {
            dropdown.innerHTML = items.map(loc => `<div class="autocomplete-item" data-id="${loc.id}">${loc.localidad}</div>`).join('');
        }
        openDropdown();
    }

    input.addEventListener('input', function() {
        const term = input.value.trim();
        hidden.value = '';
        selectedId = null;
        if (term.length < minLength || !provincia.value) { closeDropdown(); return; }
        fetch(`${endpointBuscar}?provincia_id=${provincia.value}&q=${encodeURIComponent(term)}`)
            .then(resp => resp.json())
            .then(data => {
                localidades = data;
                renderDropdown(localidades);
            });
    });

    input.addEventListener('focus', function() { if (localidades.length) renderDropdown(localidades); });

    input.addEventListener('blur', function() {
        setTimeout(() => {
            closeDropdown();
            const val = input.value.trim();
            if (!val) { hidden.value = ''; return; }
            const match = localidades.find(l => l.localidad.toLowerCase() === val.toLowerCase());
            if (match) {
                hidden.value = match.id;
            } else {
                showCrearLocalidadModal(val, provincia.options[provincia.selectedIndex]?.text || '', function(confirmar) {
                    if (confirmar) {
                        fetch(endpointCrear, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({localidad: val, provincia_id: provincia.value})
                        })
                        .then(resp => resp.json())
                        .then(data => {
                            if (data && (data.id || data.success)) {
                                hidden.value = data.id || data.id_localidad || '';
                                input.value = data.localidad || val;
                            } else {
                                hidden.value = '';
                                input.value = '';
                                alert((data && data.error) || 'Error al crear localidad');
                            }
                        }).catch(function(){ hidden.value = ''; input.value = ''; alert('Error al crear localidad'); });
                    } else {
                        hidden.value = '';
                        input.value = '';
                    }
                });
            }
        }, 200);
    });

    dropdown.addEventListener('mousedown', function(e) {
        if (e.target.classList.contains('autocomplete-item')) {
            input.value = e.target.textContent;
            hidden.value = e.target.getAttribute('data-id');
            closeDropdown();
        }
    });

    function showCrearLocalidadModal(nombre, provinciaNombre, callback) {
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
            modal.innerHTML = `<div style="background:#fff; border-radius:10px; padding:32px 28px; max-width:400px; margin:auto; box-shadow:0 2px 12px #0003; text-align:center;">
                <div class="mensaje-exito">La localidad <b>${nombre}</b> no existe en la provincia <b>${provinciaNombre}</b>.<br>¿Desea crear una localidad nueva?</div>
                <button id="btn-modal-localidad-si" class="btn-confirmar-verde">Sí</button>
                <button id="btn-modal-localidad-no" class="btn-borrar">No</button>
            </div>`;
            document.body.appendChild(modal);
        } else {
            modal.querySelector('.mensaje-exito').innerHTML = `La localidad <b>${nombre}</b> no existe en la provincia <b>${provinciaNombre}</b>.<br>¿Desea crear una localidad nueva?`;
            modal.style.display = 'flex';
        }
        document.getElementById('btn-modal-localidad-si').onclick = function() { modal.style.display = 'none'; callback(true); };
        document.getElementById('btn-modal-localidad-no').onclick = function() { modal.style.display = 'none'; callback(false); };
    }

    }
