(function (window, document) {
    "use strict";

    class ConsultarLicencias {
        constructor() {
            this.formsEliminar = document.querySelectorAll('form.form-eliminar');
            this.modal = document.getElementById('modal-confirmar-eliminacion');
            this.btnCancelar = document.getElementById('cancelar-eliminacion');
            this.btnConfirmar = document.getElementById('confirmar-eliminacion');
            this.messageCloseButtons = document.querySelectorAll('.mensaje-cerrable .cerrar-mensaje');
            this.formPendiente = null;

            this.bindEvents();
            this.bindMessageClosers();
        }

        bindEvents() {
            if (!this.formsEliminar) {
                return;
            }

            this.formsEliminar.forEach((form) => {
                if (form.dataset.confirmBound === '1') {
                    return;
                }
                form.dataset.confirmBound = '1';
                form.addEventListener('submit', (event) => {
                    event.preventDefault();
                    this.formPendiente = form;
                    this.toggleModal(true);
                });
            });

            if (this.btnCancelar && this.btnCancelar.dataset.bound !== '1') {
                this.btnCancelar.dataset.bound = '1';
                this.btnCancelar.addEventListener('click', () => {
                    this.toggleModal(false);
                    this.formPendiente = null;
                });
            }

            if (this.btnConfirmar && this.btnConfirmar.dataset.bound !== '1') {
                this.btnConfirmar.dataset.bound = '1';
                this.btnConfirmar.addEventListener('click', () => {
                    if (this.formPendiente) {
                        const formToSubmit = this.formPendiente;
                        this.formPendiente = null;
                        this.toggleModal(false);
                        window.setTimeout(() => formToSubmit.submit(), 0);
                    } else {
                        this.toggleModal(false);
                    }
                });
            }

            if (this.modal && !this.modal.dataset.overlayBound) {
                this.modal.dataset.overlayBound = '1';
                this.modal.addEventListener('click', (event) => {
                    if (event.target === this.modal) {
                        this.toggleModal(false);
                        this.formPendiente = null;
                    }
                });
            }
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

        toggleModal(show) {
            if (!this.modal) {
                return;
            }
            this.modal.setAttribute('aria-hidden', show ? 'false' : 'true');
            this.modal.classList.toggle('visible', !!show);
            document.body.classList.toggle('modal-open', !!show);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        try {
            new ConsultarLicencias();
        } catch (error) {
            console.error('Error inicializando ConsultarLicencias:', error);
        }
    });
})(window, document);
