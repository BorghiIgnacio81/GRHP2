/**
 * Componente reutilizable para búsqueda de empleados.
 * Encapsula lógica de autocompletado con teclado y ratón.
 */
class BuscadorEmpleados {
    constructor(config) {
        this.inputSelector = config.inputSelector;
        this.resultsSelector = config.resultsSelector;
        this.urlBusqueda = config.urlBusqueda;
        this.onSelect = config.onSelect || this.defaultOnSelect;
        this.minCharacters = config.minCharacters || 2;
        this.delay = config.delay || 300;
        this.placeholder = config.placeholder || 'Escriba nombre, apellido o DNI...';
        this.soloEstadoActual = config.soloEstadoActual || false;

        this.timeoutId = null;
        this.currentIndex = -1;

        this.init();
    }

    init() {
        const input = document.querySelector(this.inputSelector);
        const results = document.querySelector(this.resultsSelector);

        if (!input || !results) {
            console.error('BuscadorEmpleados: elementos no encontrados', {
                input: this.inputSelector,
                results: this.resultsSelector
            });
            return;
        }

        input.placeholder = this.placeholder;

        input.addEventListener('input', (e) => this.handleInput(e));
        input.addEventListener('keydown', (e) => this.handleKeydown(e));
        input.addEventListener('focus', (e) => this.handleFocus(e));

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !results.contains(e.target)) {
                this.hideResults();
            }
        });
    }

    handleInput(e) {
        const query = e.target.value.trim();

        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
        }

        if (query.length < this.minCharacters) {
            this.hideResults();
            return;
        }

        this.timeoutId = setTimeout(() => {
            this.buscarEmpleados(query);
        }, this.delay);
    }

    handleKeydown(e) {
    const results = document.querySelector(this.resultsSelector);
    const items = results.querySelectorAll('.empleado-item');

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.currentIndex = Math.min(this.currentIndex + 1, items.length - 1);
                this.updateSelection(items);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.currentIndex = Math.max(this.currentIndex - 1, -1);
                this.updateSelection(items);
                break;
            case 'Enter':
                e.preventDefault();
                if (this.currentIndex >= 0 && items[this.currentIndex]) {
                    this.selectEmpleado(items[this.currentIndex]);
                }
                break;
            case 'Escape':
                this.hideResults();
                break;
        }
    }

    handleFocus(e) {
        const query = e.target.value.trim();
        if (query.length >= this.minCharacters) {
            this.buscarEmpleados(query);
        }
    }

    async buscarEmpleados(query) {
        try {
            let url = `${this.urlBusqueda}?q=${encodeURIComponent(query)}`;
            if (this.soloEstadoActual) {
                url += '&solo_estado_actual=1';
            }

            const response = await fetch(url);
            const data = await response.json();

            this.mostrarResultados(data.empleados || []);
        } catch (error) {
            console.error('Error en búsqueda de empleados:', error);
            this.hideResults();
        }
    }

    mostrarResultados(empleados) {
        const results = document.querySelector(this.resultsSelector);

        if (!results) {
            return;
        }

        if (empleados.length === 0) {
            results.innerHTML = '<div class="no-results">No se encontraron empleados</div>';
            results.style.display = 'block';
            return;
        }

        const itemsHtml = empleados.map((emp, index) => `
            <li class="empleado-item" data-id="${emp.id}" data-index="${index}">
                <span class="empleado-nombre">${emp.apellido}, ${emp.nombres}</span>
                <span class="empleado-datos">DNI: ${emp.dni}${emp.email ? ' | ' + emp.email : ''}</span>
            </li>
        `).join('');

        results.innerHTML = `<ul>${itemsHtml}</ul>`;
        results.style.display = 'block';

        results.querySelectorAll('.empleado-item').forEach(item => {
            item.addEventListener('click', () => this.selectEmpleado(item));
            item.addEventListener('mouseenter', () => {
                this.currentIndex = parseInt(item.dataset.index, 10);
                this.updateSelection(results.querySelectorAll('.empleado-item'));
            });
        });

        this.currentIndex = -1;
    }

    updateSelection(items) {
        items.forEach((item, index) => {
            item.classList.toggle('selected', index === this.currentIndex);
        });
    }

    selectEmpleado(item) {
        const empleadoId = item.dataset.id;
        const empleadoData = {
            id: empleadoId,
            nombre: item.querySelector('.empleado-nombre').textContent,
            datos: item.querySelector('.empleado-datos').textContent
        };

        this.onSelect(empleadoData);
        this.hideResults();
    }

    hideResults() {
        const results = document.querySelector(this.resultsSelector);
        if (results) {
            results.style.display = 'none';
            results.innerHTML = '';
            this.currentIndex = -1;
        }
    }

    defaultOnSelect(empleadoData) {
        console.log('Empleado seleccionado:', empleadoData);
    }
}

window.BuscadorEmpleados = BuscadorEmpleados;
