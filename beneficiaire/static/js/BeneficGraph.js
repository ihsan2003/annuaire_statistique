
// Données exemple (remplacez par vos vraies données Django)
const hommesCount = {{ hommes|default: 0 }};
const femmesCount = {{ femmes|default: 0 }};

const ctxSexe = document.getElementById('BarSexe').getContext('2d');

// Configuration du graphique avec valeurs affichées
const chartConfig = {
    type: 'bar',
    data: {
        labels: ['Hommes', 'Femmes'],
        datasets: [{
            label: '',
            data: [hommesCount, femmesCount],
            backgroundColor: ['#3b82f6', '#ec4899']
        }]
    },
    options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            },
            title: {
                display: false
            },
            // Plugin pour afficher les valeurs sur les barres
            datalabels: false // Désactivé par défaut, sera activé pour l'export
        },
        scales: {
            x: {
                beginAtZero: true,
                title: {
                    display: true,
                    text: 'Nombre de bénéficiaires',
                    font: {
                        size: 12,
                        weight: 'bold'
                    }
                }
            },
            y: {
                title: {
                    display: false
                }
            }
        }
    }
};

// Créer le graphique
const myChart = new Chart(ctxSexe, chartConfig);

document.addEventListener("DOMContentLoaded", function () {
    // === Plugins globaux ===
    const outerRingPlugin = {
        id: 'outerRing',
        afterDatasetDraw(chart, args, pluginOptions) {
            const { ctx, _active } = chart;
            if (_active && _active.length > 0) {
                const arc = _active[0].element;
                ctx.save();
                ctx.beginPath();
                ctx.lineWidth = 2;
                ctx.strokeStyle = arc.options.backgroundColor;
                ctx.arc(arc.x, arc.y, arc.outerRadius + 10, arc.startAngle, arc.endAngle);
                ctx.stroke();
                ctx.restore();
            }
        }
    };

    const centerTextPlugin = {
        id: 'centerTextRev',
        beforeDraw(chart) {
            const { width, height, ctx } = chart;
            const dataset = chart.data.datasets[0].data;
            const colors = chart.data.datasets[0].backgroundColor;
            const total = dataset.reduce((a, b) => a + b, 0);
            const activeIndex = chart._active?.[0]?.index;

            // Valeur brute et label
            const value = activeIndex !== undefined ? dataset[activeIndex] : total;
            const label = activeIndex !== undefined ? chart.data.labels[activeIndex] : 'Total';
            const color = activeIndex !== undefined ? colors[activeIndex] : '#333';

            // Calcul pourcentage sans décimale inutile
            const percentRaw = total ? (value / total) * 100 : 0;
            const percent = (percentRaw % 1 === 0) ? percentRaw.toString() : percentRaw.toFixed(1);

            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            // Afficher le pourcentage au centre
            ctx.font = 'bold 28px sans-serif';
            ctx.fillStyle = color;
            ctx.fillText(percent + '%', width / 2, height / 1.9 - 30);

            // Afficher le label en dessous (avec retour à la ligne)
            ctx.font = 'bold 18px sans-serif';
            const words = label.split(' ');
            let line = '';
            const lines = [];
            const maxWidth = 140;

            for (let n = 0; n < words.length; n++) {
                const testLine = line + words[n] + ' ';
                const metrics = ctx.measureText(testLine);
                if (metrics.width > maxWidth && n > 0) {
                    lines.push(line.trim());
                    line = words[n] + ' ';
                } else {
                    line = testLine;
                }
            }
            lines.push(line.trim());

            const lineHeight = 25;
            lines.forEach((l, i) => {
                ctx.fillText(l, width / 2, height / 1.8 + (i * lineHeight));
            });

            ctx.restore();
        }
    };

    let activeIndex = -1;


    // === Chart 1: Répartition par sexe ===
    const sexeData = {
        labels: ['Hommes', 'Femmes'],
        datasets: [{
            label: 'Répartition par sexe',
            data: [{{ hommes|default: 0
        }}, {{ femmes|default: 0
}}],
    backgroundColor: ['#60A5FA', '#F472B6'],
    hoverOffset: 10,
            }]
        };

new Chart(document.getElementById('chartSexe'), {
    type: 'doughnut',
    data: sexeData,
    options: {
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
        },
        onHover: (event, elements) => {
            activeIndex = elements.length > 0 ? elements[0].index : -1;
        }
    },
    plugins: [outerRingPlugin, centerTextPlugin]
});

// === Chart 2: Répartition par population cible ===
const popLabels = {{ labels_population| safe }};
const popValues = {{ values_population| safe }};
const backgroundColors = [
    "#2E446A", "#59824A", "#A554B7", "#EEDC81", "#36A2EB",
    "#FF6384", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40",
    "#C9CBCF", "#1C2331"
];

new Chart(document.getElementById('chartPopulation'), {
    type: 'doughnut',
    data: {
        labels: [
            {% for item in population_cible_data %}
                        "{{ item.label }}"{% if not forloop.last %}, {% endif %}
    {% endfor %}
                ],
    datasets: [{
        label: 'Répartition des bénéficiaires',
        data: [
            {% for item in population_cible_data %}
                            {{ item.total }}{% if not forloop.last %}, {% endif %}
{% endfor %}
                    ],
backgroundColor: [
    '#FF6384', '#36A2EB', '#FFCE56', '#66BB6A', '#BA68C8', '#FFA726', '#8D6E63'
],
    hoverOffset: 10
                }]
            },
options: {
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
        tooltip: { enabled: true }
    },
    onHover: (event, elements) => {
        activeIndex = elements.length > 0 ? elements[0].index : -1;
    }
},
plugins: [outerRingPlugin, centerTextPlugin]
        });
    });

const ctxPop = document.getElementById('BarPopulation').getContext('2d');
new Chart(ctxPop, {
    type: 'bar',
    data: {
        labels: {{ labels_population| safe }},
    datasets: [{
        label: '',
        data: {{ values_population| safe }},
    backgroundColor: [
        "#2E446A", "#59824A", "#A554B7", "#EEDC81", "#36A2EB",
        "#FF6384", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40",
        "#C9CBCF", "#1C2331"
    ]
        }]
    },
    options: {
    responsive: true,
    plugins: {
        legend: {
            display: false
        },
        title: {
            display: false
        }
    },
    scales: {
        x: {
            beginAtZero: true,
            title: {
                display: true,
                text: 'Population cible'
            },
            ticks: {
                display: false  // cacher les valeurs (labels) de l’axe X
            }
        },
        y: {
            title: {
                display: false
            }
        }
    }
}
});


const outerRingPlugin = {
    id: 'outerRing',
    afterDatasetDraw(chart, args, pluginOptions) {
        const { ctx, _active } = chart;
        if (_active && _active.length > 0) {
            const arc = _active[0].element;
            ctx.save();
            ctx.beginPath();
            ctx.lineWidth = 2;
            ctx.strokeStyle = arc.options.backgroundColor;
            ctx.arc(arc.x, arc.y, arc.outerRadius + 10, arc.startAngle, arc.endAngle);
            ctx.stroke();
            ctx.restore();
        }
    }
};

const centerTextPlugin = {
    id: 'centerTextRev',
    beforeDraw(chart) {
        const { width, height, ctx } = chart;
        const dataset = chart.data.datasets[0].data;
        const colors = chart.data.datasets[0].backgroundColor;
        const total = dataset.reduce((a, b) => a + b, 0);
        const activeIndex = chart._active?.[0]?.index;

        const value = activeIndex !== undefined ? dataset[activeIndex] : total;
        const label = activeIndex !== undefined ? chart.data.labels[activeIndex] : 'Total';
        const color = activeIndex !== undefined ? colors[activeIndex] : '#333';

        ctx.save();
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.font = 'bold 28px sans-serif';
        ctx.fillStyle = color;
        const percent = total ? ((value / total) * 100).toFixed(1) + '%' : '0%';
        ctx.fillText(percent, width / 2, height / 1.35 - 30);


        ctx.font = 'bold 18px sans-serif';
        const words = label.split(' ');
        let line = '';
        const lines = [];
        const maxWidth = 140;

        for (let n = 0; n < words.length; n++) {
            const testLine = line + words[n] + ' ';
            const metrics = ctx.measureText(testLine);
            if (metrics.width > maxWidth && n > 0) {
                lines.push(line.trim());
                line = words[n] + ' ';
            } else {
                line = testLine;
            }
        }
        lines.push(line.trim());

        const lineHeight = 25;
        lines.forEach((l, i) => {
            ctx.fillText(l, width / 2, height / 1.8 + (i * lineHeight));
        });

        ctx.restore();
    }
};

const typeLabels = {{ labels_milieu| safe }};  // Ce sont les milieux (ex: ['Urbain', 'Rural'])
const typeValues = {{ total_milieu| safe }};   // Ce sont les valeurs correspondantes

const ChartMilieu = new Chart(document.getElementById("ChartMilieu"), {
    type: "doughnut",
    data: {
        labels: typeLabels,
        datasets: [{
            data: typeValues,
            backgroundColor: ['#2E446A', '#F4A261'],
            hoverOffset: 10
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        rotation: -90,             // départ à 12h
        circumference: 180,        // demi cercle
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
        },
        onHover: (event, elements) => {
            activeIndex = elements.length > 0 ? elements[0].index : -1;
        }
    },
    plugins: [outerRingPlugin, centerTextPlugin]
});


const labels = {{ labels_milieu_pop| safe }};
const dataUrbain = {{ urbain_values| safe }};
const dataRural = {{ rural_values| safe }};
const pourcentageUrbain = {{ pourcentage_urbain| safe }};
const pourcentageRural = {{ pourcentage_rural| safe }};

const ctxMilieu = document.getElementById('chartPopMilieu').getContext('2d');
const lineChart = new Chart(ctxMilieu, {
    type: 'line',
    data: {
        labels: labels,
        datasets: [
            {
                label: 'Milieu Urbain',
                data: dataUrbain,
                borderColor: 'blue',
                backgroundColor: 'rgba(0,0,255,0.1)',
                borderWidth: 2,
                tension: 0.4,
                fill: true,
                pointRadius: 6,
                pointHoverRadius: 10,
            },
            {
                label: 'Milieu Rural',
                data: dataRural,
                borderColor: 'green',
                backgroundColor: 'rgba(0,255,0,0.1)',
                borderWidth: 2,
                tension: 0.4,
                fill: true,
                pointRadius: 6,
                pointHoverRadius: 10,
            }
        ]
    },
    options: {
        plugins: {
            title: {
                display: false,
            },
            tooltip: {
                callbacks: {
                    label: function (context) {
                        const label = context.dataset.label || '';
                        const index = context.dataIndex;
                        const value = context.formattedValue;
                        let percentage = '';

                        if (label === 'Milieu Urbain') {
                            percentage = pourcentageUrbain[index];
                        } else if (label === 'Milieu Rural') {
                            percentage = pourcentageRural[index];
                        }

                        return `${label}: ${value} (${percentage}%)`;
                    }
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                title: {
                    display: true,
                    text: 'Nombre de bénéficiaires'
                }
            },
            x: {
                stacked: true,
                title: {
                    display: true,
                    text: 'Population ciblée'
                },
                ticks: {
                    autoSkip: false,
                    callback: function (value, index, ticks) {
                        const label = this.getLabelForValue(value);
                        // Retour à la ligne toutes les 4-5 mots ou 25 caractères
                        const words = label.split(" ");
                        const lines = [];
                        let line = "";

                        words.forEach(word => {
                            if ((line + word).length > 30) {
                                lines.push(line.trim());
                                line = word + " ";
                            } else {
                                line += word + " ";
                            }
                        });

                        if (line) lines.push(line.trim());

                        return lines;
                    }
                }
            }
        }
    }
});

setTimeout(() => {
    addExportButton("chartPopMilieu");
}, 500);

let repartitionChart;

function updateRepartitionChart() {
    const filtre = document.getElementById("repartitionFilter").value;
    const annee = "{{ selected_annee }}";
    const region = "{{ selected_region|default:'' }}";
    const delegation = "{{ selected_delegation|default:'' }}";

    const url = `/api/repartition-beneficiaires/?filtre=${filtre}&annee=${annee}&region=${region}&delegation=${delegation}`;

    fetch(url)
        .then(res => res.json())
        .then(data => {
            const ctx = document.getElementById("chartRepartitionBenefic").getContext("2d");
            if (repartitionChart) repartitionChart.destroy();

            repartitionChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: `Bénéficiaires - ${filtre}`,
                        data: data.data,
                        borderColor: '#a554b7',
                        backgroundColor: '#a554b770',
                        tension: 0.3,
                        fill: true,
                        pointBackgroundColor: '#a554b7'
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                precision: 0
                            }
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error("Erreur lors du chargement des données:", error);
        });
}

// Initialiser le graphe au chargement
window.addEventListener('DOMContentLoaded', () => {
    updateRepartitionChart();
    document.getElementById("repartitionFilter").addEventListener("change", updateRepartitionChart);
});

const labels_evolution = {{ labels_dates| safe }};

const dataSets = {
    total: {
        label: "Total",
        data: {{ values_benef| safe }},
backgroundColor: "#A554B7"
        },
hommes: {
    label: "Hommes",
        data: { { hommes_evol | safe } },
    backgroundColor: "#3B82F6"
},
femmes: {
    label: "Femmes",
        data: { { femmes_evol | safe } },
    backgroundColor: "#EC4899"
},
urbain: {
    label: "Urbain",
        data: { { urbain_evol | safe } },
    backgroundColor: "#10B981"
},
rural: {
    label: "Rural",
        data: { { rural_evol | safe } },
    backgroundColor: "#F59E0B"
},
        ...Object.fromEntries(
    Object.entries(JSON.parse(`{{ evolution_par_population|escapejs }}`)).map(([key, val], i) => [
        key, { label: key, data: val, backgroundColor: `hsl(${i * 40}, 70%, 60%)` }
    ])
)
    };

const ctx = document.getElementById('chartEvolutionBenefic').getContext('2d');
const chart = new Chart(ctx, {
    type: 'bar',
    data: {
        labels: labels_evolution,
        datasets: [dataSets["total"]]
    },
    options: {
        responsive: true,
        plugins: {
            title: {
                display: false,
            },
            legend: { display: false }
        },
        scales: {
            x: {
                title: {
                    display: true,
                    text: 'Année'
                }
            },
            y: {
                beginAtZero: true,
                title: {
                    display: true,
                    text: 'Nombre de bénéficiaires'
                }
            }
        }
    }
});

document.getElementById('evolutionFilter').addEventListener('change', function () {
    const selected = this.value;
    chart.data.datasets = [dataSets[selected]];
    chart.update();
});
