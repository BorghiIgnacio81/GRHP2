(function (window, document) {
    "use strict";

    class ConsultarLicencias {
        constructor() {
            this.formsEliminar = document.querySelectorAll('form.form-eliminar');
            this.deleteModal = document.getElementById('modal-confirmar-eliminacion');
            this.btnCancelar = document.getElementById('cancelar-eliminacion');
            this.btnConfirmar = document.getElementById('confirmar-eliminacion');
            this.reasonButtons = document.querySelectorAll('.btn-motivo-rechazo');
            this.reasonModal = document.getElementById('modal-motivo-rechazo');
            this.reasonText = document.getElementById('motivo-rechazo-texto');
            this.reasonCloseButton = document.getElementById('cerrar-motivo-rechazo');
            this.messageCloseButtons = document.querySelectorAll('.mensaje-cerrable .cerrar-mensaje');
            this.formPendiente = null;
            this.openModals = new Set();

            this.bindDeleteFlow();
            this.bindReasonFlow();
            this.bindMessageClosers();
        }

        bindDeleteFlow() {
            if (this.formsEliminar) {
                this.formsEliminar.forEach((form) => {
                    if (form.dataset.confirmBound === '1') {
                        return;
                    }
                    form.dataset.confirmBound = '1';
                    form.addEventListener('submit', (event) => {
                        event.preventDefault();
                        this.formPendiente = form;
                        this.toggleModalElement(this.deleteModal, true);
                    });
                });
            }

            if (this.btnCancelar && this.btnCancelar.dataset.bound !== '1') {
                this.btnCancelar.dataset.bound = '1';
                this.btnCancelar.addEventListener('click', () => {
                    this.toggleModalElement(this.deleteModal, false);
                    this.formPendiente = null;
                });
            }

            if (this.btnConfirmar && this.btnConfirmar.dataset.bound !== '1') {
                this.btnConfirmar.dataset.bound = '1';
                this.btnConfirmar.addEventListener('click', () => {
                    if (this.formPendiente) {
                        const formToSubmit = this.formPendiente;
                        this.formPendiente = null;
                        this.toggleModalElement(this.deleteModal, false);
                        window.setTimeout(() => formToSubmit.submit(), 0);
                    } else {
                        this.toggleModalElement(this.deleteModal, false);
                    }
                });
            }

            if (this.deleteModal && !this.deleteModal.dataset.overlayBound) {
                this.deleteModal.dataset.overlayBound = '1';
                this.deleteModal.addEventListener('click', (event) => {
                    if (event.target === this.deleteModal) {
                        this.toggleModalElement(this.deleteModal, false);
                        this.formPendiente = null;
                    }
                });
            }
        }

        bindReasonFlow() {
            if (this.reasonButtons && this.reasonButtons.length && this.reasonModal) {
                this.reasonButtons.forEach((button) => {
                    if (button.dataset.motivoBound === '1') {
                        return;
                    }
                    button.dataset.motivoBound = '1';
                    button.addEventListener('click', () => {
                        const motivo = button.getAttribute('data-motivo') || '';
                        if (this.reasonText) {
                            this.reasonText.textContent = motivo.trim() || 'Sin motivo informado.';
                        }
                        this.toggleModalElement(this.reasonModal, true);
                    });
                });
            }

            if (this.reasonCloseButton && this.reasonCloseButton.dataset.bound !== '1') {
                this.reasonCloseButton.dataset.bound = '1';
                this.reasonCloseButton.addEventListener('click', () => {
                    this.toggleModalElement(this.reasonModal, false);
                });
            }

            if (this.reasonModal && !this.reasonModal.dataset.overlayBound) {
                this.reasonModal.dataset.overlayBound = '1';
                this.reasonModal.addEventListener('click', (event) => {
                    if (event.target === this.reasonModal) {
                        this.toggleModalElement(this.reasonModal, false);
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

        toggleModalElement(modalElement, show) {
            if (!modalElement) {
                return;
            }

            modalElement.setAttribute('aria-hidden', show ? 'false' : 'true');
            modalElement.classList.toggle('visible', !!show);

            if (show) {
                this.openModals.add(modalElement);
            } else {
                this.openModals.delete(modalElement);
            }

            document.body.classList.toggle('modal-open', this.openModals.size > 0);
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
