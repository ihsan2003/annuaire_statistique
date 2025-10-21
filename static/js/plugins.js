// static/js/plugins.js

// Plugin cercle externe actif
window.outerRingPlugin = {
    id: 'outerRing',
    afterDatasetDraw(chart, args) {
        const { ctx, _active } = chart;
        if (_active?.length > 0) {
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

// Plugin texte central
window.centerTextPlugin = {
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
        ctx.fillText(Math.floor(value), width / 2, height / 1.9 - 30);

        ctx.font = 'bold 18px sans-serif';
        const words = label.split(' ');
        const lines = [];
        let line = '';
        const maxWidth = 140;

        words.forEach(word => {
            const testLine = line + word + ' ';
            if (ctx.measureText(testLine).width > maxWidth && line) {
                lines.push(line.trim());
                line = word + ' ';
            } else {
                line = testLine;
            }
        });
        lines.push(line.trim());
        const lineHeight = 25;
        lines.forEach((l, i) => {
            ctx.fillText(l, width / 2, height / 1.8 + i * lineHeight);
        });
        ctx.restore();
    }
};
