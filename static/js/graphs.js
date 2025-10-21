// graphs.js

// S'assurer que le plugin Chart.js est chargé
Chart.register(ChartDataLabels);

// Désactivation globale des datalabels
Chart.defaults.set('plugins.datalabels.display', false);

// === Chart 1 : Répartition des bénéficiaires par programme ===
function initChartProgramme() {
    const ctx = document.getElementById('chartProg');
    if (!ctx) return;

    const data = {
        labels: window.chartLabels, // injectés dans le template HTML
        datasets: [{
            label: 'Répartition par Programme',
            data: window.chartData,
            backgroundColor: window.chartColors || generateColors(window.chartLabels.length),
            hoverOffset: 10
        }]
    };

    new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: getDoughnutOptions(),
        plugins: [window.outerRingPlugin, window.centerTextPlugin]
    });
}

// === Chart 2 : Répartition des centres par programme ===
function initChartCentres() {
    const ctx = document.getElementById('chartCentres');
    if (!ctx) return;

    const data = {
        labels: window.chartCentresLabels,
        datasets: [{
            label: 'Centres par Programme',
            data: window.chartCentresCounts,
            backgroundColor: window.chartColors || generateColors(window.chartCentresLabels.length),
            hoverOffset: 10
        }]
    };

    new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: getDoughnutOptions(),
        plugins: [window.outerRingPlugin, window.centerTextPlugin]
    });
}

// === Chart 3 : Répartition par sexe (horizontal bar) ===
function initChartSexe() {
    const ctx = document.getElementById('BarSexe');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Hommes', 'Femmes'],
            datasets: [{
                data: [window.hommes || 0, window.femmes || 0],
                backgroundColor: ['#3b82f6', '#ec4899']
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: {
                legend: { display: false },
                title: { display: false }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    title: { display: true, text: 'Nombre de bénéficiaires' }
                },
                y: {
                    title: { display: false }
                }
            }
        }
    });
}

// === Chart 4 : Répartition Population cible ===
function initChartPopulation() {
    const ctx = document.getElementById('BarPopulation');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: window.labelsPopulation,
            datasets: [{
                label: 'Population cible',
                data: window.valuesPopulation,
                backgroundColor: generateColors(window.labelsPopulation.length)
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: true },
                title: { display: false }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    title: { display: true, text: 'Population cible' },
                    ticks: { display: false }
                },
                y: {
                    title: { display: false }
                }
            }
        }
    });
}

// === Chart 5 : Répartition des centres (barres) ===
function initChartCentreBar() {
    const ctx = document.getElementById('chartCentreProg');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: window.chartCentresLabels,
            datasets: [{
                label: 'Nombre de centres',
                data: window.chartCentresCounts,
                backgroundColor: '#10b981'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { mode: 'index', intersect: false }
            },
            scales: {
                x: {
                    stacked: true,
                    title: { display: true, text: 'Programmes' },
                    ticks: {
                        autoSkip: false,
                        callback: wrapLabel
                    }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Nombre de centres' }
                }
            }
        }
    });
}

// === Fonction utilitaire pour les options Doughnut ===
function getDoughnutOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        layout: { padding: 30 },
        animation: {
            animateRotate: true,
            animateScale: true,
            duration: 350,
            easing: 'easeOutBounce'
        },
        plugins: {
            legend: { display: false },
            tooltip: {
                enabled: true,
                callbacks: {
                    label: function (context) {
                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                        const value = context.parsed;
                        const percent = total ? ((value / total) * 100).toFixed(1) + '%' : '0%';
                        return `${context.label}: ${value} (${percent})`;
                    }
                }
            }
        }
    };
}

// === Fonction utilitaire : Génération automatique de couleurs ===
function generateColors(count) {
    const colors = [
        "#2E446A", "#59824A", "#A554B7", "#EEDC81", "#36A2EB",
        "#FF6384", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40",
        "#C9CBCF", "#1C2331", "#66BB6A", "#BA68C8", "#FFA726",
        "#8D6E63", "#F06292", "#7E57C2", "#0097A7", "#D4E157"
    ];
    return Array.from({ length: count }, (_, i) => colors[i % colors.length]);
}

// === Fonction utilitaire pour retour à la ligne sur labels ===
function wrapLabel(value, index, ticks) {
    const label = this.getLabelForValue(value);
    const words = label.split(" ");
    const lines = [];
    let line = "";

    words.forEach(word => {
        if ((line + word).length > 25) {
            lines.push(line.trim());
            line = word + " ";
        } else {
            line += word + " ";
        }
    });

    if (line) lines.push(line.trim());
    return lines;
}
