/**
 * Módulo para el dashboard de empleado
 * PROTOCOLO1 MODULARIZADO: Charts y funcionalidad extraída
 */
class DashboardEmpleadoModule {
    constructor(config = {}) {
        this.config = {
            licenciasElementId: 'misLicenciasPie',
            vacacionesElementId: 'misVacacionesPie',
            licenciasCenterText: 'Mis\nLicencias',
            vacacionesCenterText: 'Mis\nVacaciones',
            licenciasUrl: '/nucleo/consultar_licencia/?filtro_tipo=licencias',
            vacacionesUrl: '/nucleo/consultar_licencia/?filtro_tipo=vacaciones',
            licenciasData: {
                labels: ['Aprobadas', 'En espera', 'Rechazadas'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#4caf50', '#ffe066', '#e57373']
                }]
            },
            vacacionesData: {
                labels: ['Disponibles', 'En Espera', 'Aprobadas'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#007bff', '#ffc107', '#28a745']
                }]
            },
            ...config
        };
        this.charts = {};
        this.pluginRegistered = false;
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
        if (typeof Chart === 'undefined') {
            console.error('Chart.js no está disponible para DashboardEmpleadoModule');
            return;
        }
        this.registerChartPlugin();
        this.initializeCharts();
    }

    registerChartPlugin() {
        if (this.pluginRegistered || (Chart.registry && Chart.registry.plugins.get('centerText'))) {
            this.pluginRegistered = true;
            return;
        }
        const centerTextPlugin = {
            id: 'centerText',
            beforeDraw(chart) {
                const pluginConfig = chart.config.options.plugins && chart.config.options.plugins.centerText;
                if (!pluginConfig || !pluginConfig.text) return;

                const ctx = chart.ctx;
                const { width, height } = chart;
                const lines = String(pluginConfig.text).split('\n');
                const lineHeight = 22;
                const totalHeight = lineHeight * lines.length;
                let y = height / 2 - totalHeight / 2 + lineHeight / 2 - 22;

                ctx.save();
                ctx.font = 'bold 18px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = '#222';

                lines.forEach(line => {
                    ctx.fillText(line, width / 2, y);
                    y += lineHeight;
                });

                ctx.restore();
            }
        };

        Chart.register(centerTextPlugin);
        this.pluginRegistered = true;
    }

    initializeCharts() {
        this.initPieChart(
            this.config.licenciasElementId,
            this.config.licenciasData,
            this.config.licenciasCenterText,
            this.config.licenciasUrl,
            'misLicencias'
        );
        this.initPieChart(
            this.config.vacacionesElementId,
            this.config.vacacionesData,
            this.config.vacacionesCenterText,
            this.config.vacacionesUrl,
            'misVacaciones'
        );
    }

    initPieChart(elementId, data, centerText, redirectUrl, chartKey) {
        const canvas = document.getElementById(elementId);
        if (!canvas) {
            console.warn(`DashboardEmpleadoModule: no se encontró el elemento ${elementId}`);
            return;
        }
        const ctx = canvas.getContext('2d');

        this.charts[chartKey] = new Chart(ctx, {
            type: 'doughnut',
            data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true,
                            font: { size: 11 }
                        }
                    },
                    centerText: { text: centerText }
                },
                cutout: '68%'
            }
        });

        canvas.addEventListener('click', () => {
            if (redirectUrl) {
                window.location.href = redirectUrl;
            }
        });
    }

    updateChartData(chartKey, newConfig) {
        const chart = this.charts[chartKey];
        if (!chart) return;
        if (newConfig.data) {
            chart.data = newConfig.data;
        }
        if (newConfig.centerText) {
            chart.options.plugins.centerText.text = newConfig.centerText;
        }
        chart.update();
    }

    setConfig(config) {
        this.config = { ...this.config, ...config };
        this.initializeCharts();
    }
}

window.DashboardEmpleadoModule = DashboardEmpleadoModule;
