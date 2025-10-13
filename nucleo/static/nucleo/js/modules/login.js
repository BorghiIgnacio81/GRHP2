/**
 * PROTOCOLO1 MODULARIZADO: JavaScript para login.html
 * Manejo de modales, navegación y validación de login
 */

class LoginModule {
    constructor(config = {}) {
        this.config = {
            urls: {},
            user: null,
            flags: {},
            ...config
        };
        this.init();
    }

    init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.onReady());
        } else {
            this.onReady();
        }
    }

    onReady() {
        this.setupBackForwardDetection();
        this.setupLogoutModal();
        this.setupBlockedModal();
        this.setupBlockModal();
        this.setupSuccessModal();
        this.clearFormFields();
    }

    setConfig(config) {
        this.config = { ...this.config, ...config };
        if (document.readyState !== 'loading') {
            this.onReady();
        }
    }

    setupBackForwardDetection() {
        if (this.config.flags.isAuthenticated && !this.config.flags.showLogoutModal) {
            const entries = performance ? performance.getEntriesByType('navigation') : [];
            if (entries && entries[0] && entries[0].type === 'back_forward') {
                window.location.replace(this.config.urls.loginWithLogoutModal);
            }
        }
    }

    setupLogoutModal() {
        if (!this.config.flags.showLogoutModal) return;

        const confirmBtn = document.getElementById('confirm-logout');
        const cancelBtn = document.getElementById('cancel-logout');
        const logoutForm = document.getElementById('logout-form');

        if (confirmBtn && logoutForm) {
            confirmBtn.onclick = () => logoutForm.submit();
        }

        if (cancelBtn) {
            cancelBtn.onclick = () => {
                const redirectUrl = this.config.user && this.config.user.isStaff
                    ? this.config.urls.dashboardGestor
                    : this.config.urls.dashboardEmpleado;
                window.location.href = redirectUrl || this.config.urls.login;
            };
        }
    }

    setupBlockedModal() {
        if (!this.config.flags.blockedMessage) return;

        const okBtn = document.getElementById('blocked-ok');
        const modal = document.getElementById('blocked-modal');

        if (okBtn && modal) {
            okBtn.onclick = () => {
                modal.style.display = 'none';
            };
        }
    }

    setupBlockModal() {
        if (!this.config.flags.showBlockModal) return;

        const modal = document.getElementById('block-modal');
        const resetBtn = document.getElementById('block-reset-password');
        const okBtn = document.getElementById('block-ok');

        if (resetBtn) {
            resetBtn.onclick = () => {
                window.location.href = this.config.urls.passwordReset;
            };
        }

        if (okBtn && modal) {
            okBtn.onclick = () => {
                modal.style.display = 'none';
            };
        }
    }

    setupSuccessModal() {
        if (!this.config.flags.passwordResetSuccess) return;

        const modal = document.getElementById('success-modal');
        const okBtn = document.getElementById('success-ok');

        if (okBtn && modal) {
            okBtn.onclick = () => {
                modal.style.display = 'none';
                window.history.replaceState({}, document.title, this.config.urls.login);
            };
        }
    }

    clearFormFields() {
        window.onload = () => {
            const userField = document.querySelector('input[name="username"]');
            const passField = document.querySelector('input[name="password"]');

            if (userField) userField.value = '';
            if (passField) passField.value = '';
        };
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'flex';
        }
    }

    hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    }
}

function initLoginModule(config) {
    if (window.loginModule instanceof LoginModule) {
        window.loginModule.setConfig(config);
    } else {
        window.loginModule = new LoginModule(config);
    }
}

window.LoginModule = LoginModule;
window.initLoginModule = initLoginModule;
