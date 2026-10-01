// Configuration globale
const PDF_CONFIG = {
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
    margins: {
        top: 25,
        right: 20,
        bottom: 25,
        left: 20
    },
    colors: {
        primary: [165, 84, 183],
        secondary: [52, 73, 94],
        success: [39, 174, 96],
        text: [44, 62, 80],
        light: [236, 240, 241],
        white: [255, 255, 255]
    },
    logoPath: '/static/images/logo.png'
};

// Vérification de l'espace disponible
function checkPageSpace(pdf, currentY, requiredHeight) {
    const pageHeight = pdf.internal.pageSize.getHeight();
    const availableSpace = pageHeight - PDF_CONFIG.margins.bottom - currentY - 15;
    return {
        hasSpace: availableSpace >= requiredHeight,
        availableSpace: availableSpace,
        requiredHeight: requiredHeight
    };
}

// Assurer l'espace sur la page
function ensurePageSpace(pdf, currentY, requiredHeight, pageNumber, totalPages) {
    const spaceCheck = checkPageSpace(pdf, currentY, requiredHeight);
    
    if (!spaceCheck.hasSpace) {
        addFooter(pdf, pageNumber, totalPages);
        pdf.addPage();
        pageNumber++;
        currentY = addHeader(pdf, 'SUITE...', pageNumber, false);
        currentY += 10;
    }
    return { currentY, pageNumber };
}

// Découper le texte en lignes
function splitTextToLines(pdf, text, maxWidth) {
    if (!text || maxWidth <= 0) return [''];
    
    const words = String(text).trim().split(' ');
    const lines = [];
    let currentLine = '';
    
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(10);
    
    for (let word of words) {
        const testLine = currentLine ? `${currentLine} ${word}` : word;
        const textWidth = pdf.getTextWidth(testLine);
        
        if (textWidth <= maxWidth) {
            currentLine = testLine;
        } else {
            if (currentLine) {
                lines.push(currentLine);
                currentLine = word;
            } else {
                if (pdf.getTextWidth(word) > maxWidth) {
                    let partialWord = '';
                    for (let char of word) {
                        const testChar = partialWord + char;
                        if (pdf.getTextWidth(testChar) <= maxWidth) {
                            partialWord = testChar;
                        } else {
                            if (partialWord) lines.push(partialWord);
                            partialWord = char;
                        }
                    }
                    if (partialWord) currentLine = partialWord;
                } else {
                    currentLine = word;
                }
            }
        }
    }
    
    if (currentLine) {
        lines.push(currentLine);
    }
    
    return lines.length > 0 ? lines : [''];
}

// Calculer la hauteur d'une ligne avec texte multiligne
function calculateRowHeight(pdf, row, columnWidths, baseRowHeight = 8) {
    let maxLines = 1;
    
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(10);
    
    row.forEach((cell, colIndex) => {
        const cellWidth = columnWidths[colIndex] - 6;
        const lines = splitTextToLines(pdf, cell, cellWidth);
        maxLines = Math.max(maxLines, lines.length);
    });
    
    return Math.max(baseRowHeight, maxLines * 4 + 4);
}

// Fonctions utilitaires
function formatNumber(number) {
    if (typeof number !== 'number') return '0';
    return new Intl.NumberFormat('fr-FR', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
        useGrouping: true
    }).format(number).replace(/\s/g, ' ');
}

function calculatePercentage(value, total) {
    if (total === 0) return '0,0';
    const percent = (value / total) * 100;
    const formatted = percent % 1 === 0 ? percent.toString() : percent.toFixed(1);
    return formatted.replace('.', ',');
}

// Ajouter un en-tête de page (MODIFIÉ)
function addHeader(pdf, title, pageNumber = null) {
    const pageWidth = pdf.internal.pageSize.getWidth();
    
    pdf.setFillColor(...PDF_CONFIG.colors.primary);
    pdf.rect(0, 0, pageWidth, 8, 'F');
    
    pdf.setFontSize(16);
    pdf.setTextColor(...PDF_CONFIG.colors.primary);
    pdf.setFont('helvetica', 'bold');
    pdf.text(title, PDF_CONFIG.margins.left, PDF_CONFIG.margins.top);
    
    pdf.setFontSize(9);
    pdf.setTextColor(...PDF_CONFIG.colors.text);
    const currentDate = new Date().toLocaleDateString('fr-FR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
    pdf.text(`Généré le: ${currentDate}`, PDF_CONFIG.margins.left, PDF_CONFIG.margins.top + 8);
    
    pdf.setDrawColor(...PDF_CONFIG.colors.light);
    pdf.setLineWidth(0.5);
    pdf.line(PDF_CONFIG.margins.left, PDF_CONFIG.margins.top + 12, 
            pageWidth - PDF_CONFIG.margins.right, PDF_CONFIG.margins.top + 12);
    
    return PDF_CONFIG.margins.top + 20;
}

// Ajouter un pied de page
function addFooter(pdf, pageNumber, totalPages) {
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    
    pdf.setDrawColor(...PDF_CONFIG.colors.light);
    pdf.setLineWidth(0.5);
    pdf.line(PDF_CONFIG.margins.left, pageHeight - PDF_CONFIG.margins.bottom + 5, 
            pageWidth - PDF_CONFIG.margins.right, pageHeight - PDF_CONFIG.margins.bottom + 5);
    
    pdf.setFontSize(8);
    pdf.setTextColor(...PDF_CONFIG.colors.secondary);
    pdf.setFont('helvetica', 'normal');
    pdf.text('Dashboard des statistiques - Rapport d\'analyse', 
            PDF_CONFIG.margins.left, pageHeight - PDF_CONFIG.margins.bottom + 10);
    
    const pageText = `${pageNumber} / ${totalPages}`;
    const textWidth = pdf.getTextWidth(pageText);
    pdf.text(pageText, (pageWidth - textWidth) / 2, pageHeight - PDF_CONFIG.margins.bottom + 10);
}

// Ajouter une section avec titre
function addSectionTitle(pdf, title, yPosition) {
    pdf.setFontSize(14);
    pdf.setTextColor(...PDF_CONFIG.colors.secondary);
    pdf.setFont('helvetica', 'bold');
    pdf.text(title, PDF_CONFIG.margins.left, yPosition);
    
    const titleWidth = pdf.getTextWidth(title);
    pdf.setDrawColor(...PDF_CONFIG.colors.primary);
    pdf.setLineWidth(1);
    pdf.line(PDF_CONFIG.margins.left, yPosition + 2, 
            PDF_CONFIG.margins.left + titleWidth, yPosition + 2);
    
    return yPosition + 10;
}

// Fonction pour charger le logo en base64
async function loadLogoAsBase64(logoPath) {
    try {
        const response = await fetch(logoPath);
        const blob = await response.blob();
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    } catch (error) {
        console.error('Erreur lors du chargement du logo:', error);
        return null;
    }
}

// Fonction principale pour les tableaux longs avec pagination
function addDataTable(pdf, headers, data, yPosition, options = {}) {
    const pageWidth = pdf.internal.pageSize.getWidth();
    const tableWidth = pageWidth - (PDF_CONFIG.margins.left + PDF_CONFIG.margins.right);
    const baseRowHeight = options.rowHeight || 8;
    let { pageNumber = 1, totalPages = 1 } = options;
    
    let columnWidths;
    if (options.columnWidths) {
        columnWidths = options.columnWidths;
    } else {
        if (headers.length === 3 && headers[0].toLowerCase().includes('catégorie')) {
            columnWidths = [
                tableWidth * 0.5,
                tableWidth * 0.25,
                tableWidth * 0.25
            ];
        } else if (headers.length === 2) {
            columnWidths = [
                tableWidth * 0.6,
                tableWidth * 0.4
            ];
        } else {
            const colWidth = tableWidth / headers.length;
            columnWidths = Array(headers.length).fill(colWidth);
        }
    }
    
    const currentFont = pdf.internal.getFont();
    const currentFontSize = pdf.internal.getFontSize();
    
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(10);
    
    const headerHeight = calculateRowHeight(pdf, headers, columnWidths, baseRowHeight);
    
    let currentY = yPosition;
    let isFirstPage = true;
    let dataIndex = 0;
    
    while (dataIndex < data.length || isFirstPage) {
        
        if (!isFirstPage) {
            addFooter(pdf, pageNumber, totalPages);
            pdf.addPage();
            pageNumber++;
            currentY = addHeader(pdf, 'SUITE DU TABLEAU...', pageNumber, false);
            currentY += 5;
        }
        
        // Dessiner l'en-tête du tableau
        pdf.setFillColor(...PDF_CONFIG.colors.primary);
        pdf.rect(PDF_CONFIG.margins.left, currentY, tableWidth, headerHeight, 'F');
        
        pdf.setFontSize(10);
        pdf.setTextColor(...PDF_CONFIG.colors.white);
        pdf.setFont('helvetica', 'bold');
        
        let currentX = PDF_CONFIG.margins.left;
        headers.forEach((header, index) => {
            const cellWidth = columnWidths[index] - 6;
            const lines = splitTextToLines(pdf, header, cellWidth);
            
            const lineHeight = 4;
            const totalTextHeight = lines.length * lineHeight;
            const startY = currentY + (headerHeight - totalTextHeight) / 2 + lineHeight;
            
            lines.forEach((line, lineIndex) => {
                pdf.text(line, currentX + 3, startY + (lineIndex * lineHeight));
            });
            
            currentX += columnWidths[index];
        });
        
        currentY += headerHeight;
        
        const pageHeight = pdf.internal.pageSize.getHeight();
        const availableSpaceForData = pageHeight - PDF_CONFIG.margins.bottom - currentY - 20;
        
        let rowsToProcess = [];
        let totalHeightUsed = 0;
        
        for (let i = dataIndex; i < data.length; i++) {
            const rowHeight = calculateRowHeight(pdf, data[i], columnWidths, baseRowHeight);
            
            if (totalHeightUsed + rowHeight <= availableSpaceForData) {
                rowsToProcess.push({
                    data: data[i],
                    height: rowHeight,
                    index: i
                });
                totalHeightUsed += rowHeight;
            } else {
                break;
            }
        }
        
        if (rowsToProcess.length === 0 && !isFirstPage) {
            break;
        }
        
        pdf.setFont('helvetica', 'normal');
        pdf.setTextColor(...PDF_CONFIG.colors.text);
        
        rowsToProcess.forEach((rowInfo, rowIndex) => {
            const row = rowInfo.data;
            const rowHeight = rowInfo.height;
            
            if (rowIndex % 2 === 0) {
                pdf.setFillColor(...PDF_CONFIG.colors.light);
                pdf.rect(PDF_CONFIG.margins.left, currentY, tableWidth, rowHeight, 'F');
            }
            
            currentX = PDF_CONFIG.margins.left;
            row.forEach((cell, colIndex) => {
                let formattedCell = String(cell);
                
                if (colIndex === 1 && headers[colIndex]?.toLowerCase().includes('nombre')) {
                    const cleanedValue = String(cell).replace(/\s/g, '').replace(/[^\d]/g, '');
                    const numValue = parseInt(cleanedValue);
                    if (!isNaN(numValue) && numValue > 0) {
                        formattedCell = formatNumber(numValue);
                    }
                }
                
                const cellWidth = columnWidths[colIndex] - 6;
                const lines = splitTextToLines(pdf, formattedCell, cellWidth);
                
                const lineHeight = 4;
                const totalTextHeight = lines.length * lineHeight;
                const startY = currentY + (rowHeight - totalTextHeight) / 2 + lineHeight;
                
                lines.forEach((line, lineIndex) => {
                    if (colIndex === 0) {
                        pdf.text(line, currentX + 3, startY + (lineIndex * lineHeight));
                    } else if (headers[colIndex]?.toLowerCase().includes('pourcentage') || 
                            headers[colIndex]?.toLowerCase().includes('%')) {
                        const textWidth = pdf.getTextWidth(line);
                        pdf.text(line, currentX + columnWidths[colIndex] - textWidth - 3, startY + (lineIndex * lineHeight));
                    } else {
                        const textWidth = pdf.getTextWidth(line);
                        pdf.text(line, currentX + columnWidths[colIndex] - textWidth - 3, startY + (lineIndex * lineHeight));
                    }
                });
                
                currentX += columnWidths[colIndex];
            });
            
            currentY += rowHeight;
        });
        
        const sectionHeight = headerHeight + totalHeightUsed;
        const sectionStartY = currentY - totalHeightUsed - headerHeight;
        
        pdf.setDrawColor(...PDF_CONFIG.colors.secondary);
        pdf.setLineWidth(0.5);
        
        pdf.rect(PDF_CONFIG.margins.left, sectionStartY, tableWidth, sectionHeight, 'S');
        
        let tempY = sectionStartY + headerHeight;
        rowsToProcess.forEach((rowInfo) => {
            pdf.line(PDF_CONFIG.margins.left, tempY, PDF_CONFIG.margins.left + tableWidth, tempY);
            tempY += rowInfo.height;
        });
        
        currentX = PDF_CONFIG.margins.left;
        for (let i = 0; i < columnWidths.length - 1; i++) {
            currentX += columnWidths[i];
            pdf.line(currentX, sectionStartY, currentX, sectionStartY + sectionHeight);
        }
        
        dataIndex += rowsToProcess.length;
        isFirstPage = false;
        
        if (dataIndex >= data.length) {
            break;
        }
    }
    
    pdf.setFont(currentFont.fontName, currentFont.fontStyle);
    pdf.setFontSize(currentFontSize);
    
    return { currentY: currentY + 5, pageNumber };
}

// Générer les statistiques d'un graphique doughnut/pie
function generateDoughnutStats(chart) {
    const data = chart.data.datasets[0].data;
    const labels = chart.data.labels;
    const total = data.reduce((a, b) => a + b, 0);
    
    return {
        type: 'doughnut',
        total: total,
        data: labels.map((label, index) => ({
            label: label,
            value: data[index],
            percentage: calculatePercentage(data[index], total)
        }))
    };
}

// Générer les statistiques d'un graphique en barres
function generateBarStats(chart) {
    const datasets = chart.data.datasets;
    const labels = chart.data.labels;
    
    return {
        type: 'bar',
        datasets: datasets.map(dataset => {
            const total = dataset.data.reduce((a, b) => a + b, 0);
            return {
                label: dataset.label || 'Données',
                total: total,
                data: labels.map((label, index) => ({
                    label: label,
                    value: dataset.data[index],
                    percentage: calculatePercentage(dataset.data[index], total)
                }))
            };
        })
    };
}

// Générer les statistiques d'un graphique linéaire
function generateLineStats(chart) {
    const datasets = chart.data.datasets;
    const labels = chart.data.labels;
    
    return {
        type: 'line',
        datasets: datasets.map(dataset => {
            const data = dataset.data;
            const total = data.reduce((a, b) => a + b, 0);
            const average = total / data.length;
            const max = Math.max(...data);
            const min = Math.min(...data);
            
            return {
                label: dataset.label || 'Série',
                total: total,
                average: Math.round(average),
                max: max,
                min: min,
                data: labels.map((label, index) => ({
                    label: label,
                    value: data[index]
                }))
            };
        })
    };
}

// Ajouter les statistiques au PDF
function addChartStats(pdf, stats, yPosition, pageInfo = { pageNumber: 1, totalPages: 1 }) {
    let currentY = yPosition;
    let { pageNumber, totalPages } = pageInfo;
    
    if (stats.type === 'doughnut') {
        let spaceCheck = ensurePageSpace(pdf, currentY, 25, pageNumber, totalPages);
        currentY = spaceCheck.currentY;
        pageNumber = spaceCheck.pageNumber;
        
        currentY = addSectionTitle(pdf, 'Résumé des données', currentY);
        
        pdf.setFontSize(11);
        pdf.setTextColor(...PDF_CONFIG.colors.text);
        pdf.setFont('helvetica', 'bold');
        pdf.text(`Total: ${formatNumber(stats.total)}`, 
                PDF_CONFIG.margins.left, currentY);
        currentY += 10;
        
        currentY = addSectionTitle(pdf, 'Répartition détaillée', currentY);
        
        const headers = ['Catégorie', 'Valeur', 'Pourcentage'];
        const tableData = stats.data.map(item => [
            item.label,
            item.value,
            item.percentage + '%'
        ]);
        
        const tableResult = addDataTable(pdf, headers, tableData, currentY, {
            pageNumber,
            totalPages
        });
        currentY = tableResult.currentY;
        pageNumber = tableResult.pageNumber;
        
    } else if (stats.type === 'bar') {
        stats.datasets.forEach((dataset, index) => {
            let spaceCheck = ensurePageSpace(pdf, currentY, 40, pageNumber, totalPages);
            currentY = spaceCheck.currentY;
            pageNumber = spaceCheck.pageNumber;
            
            currentY = addSectionTitle(pdf, `Analyse - ${dataset.label}`, currentY);
            
            pdf.setFontSize(11);
            pdf.setTextColor(...PDF_CONFIG.colors.text);
            pdf.setFont('helvetica', 'bold');
            pdf.text(`Total: ${formatNumber(dataset.total)}`, 
                    PDF_CONFIG.margins.left, currentY);
            currentY += 10;
            
            const headers = ['Catégorie', 'Valeur', 'Pourcentage'];
            const tableData = dataset.data.map(item => [
                item.label,
                item.value,
                item.percentage + '%'
            ]);
            
            const tableResult = addDataTable(pdf, headers, tableData, currentY, {
                pageNumber,
                totalPages
            });
            currentY = tableResult.currentY + 5;
            pageNumber = tableResult.pageNumber;
        });
        
    } else if (stats.type === 'line') {
        stats.datasets.forEach((dataset, index) => {
            let spaceCheck = ensurePageSpace(pdf, currentY, 50, pageNumber, totalPages);
            currentY = spaceCheck.currentY;
            pageNumber = spaceCheck.pageNumber;
            
            currentY = addSectionTitle(pdf, `Évolution - ${dataset.label}`, currentY);
            
            pdf.setFontSize(10);
            pdf.setTextColor(...PDF_CONFIG.colors.text);
            pdf.setFont('helvetica', 'normal');
            
            const statsText = [
                `Total: ${formatNumber(dataset.total)}`,
                `Moyenne: ${formatNumber(dataset.average)}`,
                `Maximum: ${formatNumber(dataset.max)}`,
                `Minimum: ${formatNumber(dataset.min)}`
            ];
            
            statsText.forEach((text, i) => {
                pdf.text(text, PDF_CONFIG.margins.left + (i % 2) * 90, 
                        currentY + Math.floor(i / 2) * 6);
            });
            currentY += 15;
            
            const headers = ['Période', 'Valeur'];
            const tableData = dataset.data.map(item => [
                item.label,
                item.value
            ]);
            
            const tableResult = addDataTable(pdf, headers, tableData, currentY, {
                pageNumber,
                totalPages
            });
            currentY = tableResult.currentY + 5;
            pageNumber = tableResult.pageNumber;
        });
    }
    
    return { currentY, pageNumber };
}

// Optimiser l'image du graphique
function optimizeChartImage(canvas, maxWidth = 700, quality = 0.85) {
    try {
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        
        const aspectRatio = canvas.height / canvas.width;
        const newWidth = Math.min(canvas.width, maxWidth);
        const newHeight = newWidth * aspectRatio;
        
        tempCanvas.width = newWidth;
        tempCanvas.height = newHeight;
        
        tempCtx.fillStyle = '#ffffff';
        tempCtx.fillRect(0, 0, newWidth, newHeight);
        
        tempCtx.drawImage(canvas, 0, 0, newWidth, newHeight);
        
        return tempCanvas.toDataURL('image/jpeg', quality);
    } catch (error) {
        return canvas.toDataURL('image/png', quality);
    }
}

// Exporter un graphique individuel
async function exportChartToPDF(canvasId, title, chartType) {
    try {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            showErrorMessage(`Canvas ${canvasId} non trouvé`);
            return;
        }

        const chart = Chart.getChart(canvas);
        if (!chart) {
            showErrorMessage(`Graphique ${canvasId} non initialisé`);
            return;
        }

        if (!window.jspdf) {
            showErrorMessage('jsPDF non chargé');
            return;
        }

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF({
            orientation: PDF_CONFIG.orientation,
            unit: PDF_CONFIG.unit,
            format: PDF_CONFIG.format
        });
        
        let currentPage = 1;
        let estimatedTotalPages = 5;
        
        let currentY = addHeader(pdf, title, currentPage, false);
        currentY += 10;
        
        const chartImage = optimizeChartImage(canvas);
        const pageWidth = pdf.internal.pageSize.getWidth();
        const availableWidth = pageWidth - (PDF_CONFIG.margins.left + PDF_CONFIG.margins.right);
        const chartWidth = availableWidth * 0.9;
        const aspectRatio = canvas.height / canvas.width;
        let chartHeight = chartWidth * aspectRatio;
        
        const maxChartHeight = 90;
        if (chartHeight > maxChartHeight) {
            chartHeight = maxChartHeight;
        }
        
        const chartX = (pageWidth - chartWidth) / 2;
        
        pdf.addImage(chartImage, 'JPEG', chartX, currentY, chartWidth, chartHeight);
        currentY += chartHeight + 15;
        
        let stats;
        switch (chartType.toLowerCase()) {
            case 'doughnut':
            case 'pie':
                stats = generateDoughnutStats(chart);
                break;
            case 'bar':
                stats = generateBarStats(chart);
                break;
            case 'line':
                stats = generateLineStats(chart);
                break;
        }
        
        if (stats) {
            const statsResult = addChartStats(pdf, stats, currentY, {
                pageNumber: currentPage,
                totalPages: estimatedTotalPages
            });
            currentY = statsResult.currentY;
            currentPage = statsResult.pageNumber;
        }
        
        const finalTotalPages = currentPage;
        
        addFooter(pdf, currentPage, finalTotalPages);
        
        const fileName = `${title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_${Date.now()}.pdf`;
        pdf.save(fileName);
        
        showSuccessMessage(`PDF exporté: ${fileName} (${finalTotalPages} pages)`);
        
    } catch (error) {
        showErrorMessage(`Erreur: ${error.message}`);
    }
}

// Fonction principale d'exportation globale (MODIFIÉE)
async function exportAllChartsToPDF() {
    try {
        if (!window.jspdf) {
            showErrorMessage('jsPDF non chargé');
            return;
        }

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF({
            orientation: PDF_CONFIG.orientation,
            unit: PDF_CONFIG.unit,
            format: PDF_CONFIG.format
        });
        
        const chartConfigs = [
            { id: 'chartSexe', title: 'Répartition par Sexe', type: 'doughnut', category: 'bénéficiaires' },
            { id: 'chartPopulation', title: 'Répartition par Population Cible', type: 'doughnut', category: 'bénéficiaires' },
            { id: 'BarSexe', title: 'Distribution par Sexe', type: 'bar', category: 'bénéficiaires' },
            { id: 'BarPopulation', title: 'Distribution par Population', type: 'bar', category: 'bénéficiaires' },
            { id: 'ChartMilieu', title: 'Répartition par Milieu', type: 'doughnut', category: 'bénéficiaires' },
            { id: 'chartPopMilieu', title: 'Évolution Population/Milieu', type: 'line', category: 'bénéficiaires' },
            { id: 'chartRepartitionBenefic', title: 'Répartition des Bénéficiaires', type: 'line', category: 'bénéficiaires' },
            { id: 'chartEvolutionBenefic', title: 'Évolution des Bénéficiaires', type: 'bar', category: 'bénéficiaires' },
            { id: 'chartCentreMilieu', title: 'Répartition des Centres par Milieu', type: 'doughnut', category: 'centres' },
            { id: 'chartCentre', title: 'Nombre des Centres par Milieu', type: 'bar', category: 'centres' },
            { id: 'chartRepartitionCentre', title: 'Répartition des Centres', type: 'line', category: 'centres' },
            { id: 'chartEvolutionCentre', title: 'Évolution des Centres', type: 'bar', category: 'centres' }
        ];
        
        const availableCharts = [];
        chartConfigs.forEach(config => {
            const canvas = document.getElementById(config.id);
            const chart = Chart.getChart(canvas);
            if (canvas && chart) {
                availableCharts.push({
                    ...config,
                    canvas,
                    chart
                });
            }
        });
        
        if (availableCharts.length === 0) {
            showErrorMessage('Aucun graphique disponible pour l\'exportation');
            return;
        }
        
        const chartsByCategory = availableCharts.reduce((acc, chart) => {
            if (!acc[chart.category]) acc[chart.category] = [];
            acc[chart.category].push(chart);
            return acc;
        }, {});
        
        let estimatedTotalPages = availableCharts.length + 3;
        let currentPage = 1;
        
        // PAGE DE COUVERTURE AVEC LOGO (MODIFIÉE)
        let currentY = addHeader(pdf, 'RAPPORT STATISTIQUE COMPLET', currentPage, true); // Afficher date/heure
        currentY += 10;
        
        // Charger et ajouter le logo au centre
        const logoBase64 = await loadLogoAsBase64(PDF_CONFIG.logoPath);
        if (logoBase64) {
            const pageWidth = pdf.internal.pageSize.getWidth();
            const logoWidth = 100; // Largeur du logo en mm
            const logoHeight = 15; // Hauteur du logo en mm
            const logoX = (pageWidth - logoWidth) / 2; // Centrer horizontalement
            
            pdf.addImage(logoBase64, 'PNG', logoX, currentY, logoWidth, logoHeight);
            currentY += logoHeight + 50;
        }
        
        pdf.setFontSize(24);
        pdf.setTextColor(...PDF_CONFIG.colors.primary);
        pdf.setFont('helvetica', 'bold');
        pdf.text('ANALYSE COMPLÈTE', PDF_CONFIG.margins.left, currentY);
        currentY += 12;
        
        pdf.setFontSize(20);
        pdf.text('BÉNÉFICIAIRES & CENTRES', PDF_CONFIG.margins.left, currentY);
        currentY += 14;
        
        pdf.setFontSize(16);
        pdf.setTextColor(...PDF_CONFIG.colors.secondary);
        pdf.setFont('helvetica', 'normal');
        pdf.text('Rapport statistique détaillé avec analyses visuelles', PDF_CONFIG.margins.left, currentY);
        currentY += 30;
        
        const reportInfo = [
            `Graphiques des bénéficiaires: ${chartsByCategory.bénéficiaires?.length || 0}`,
            `Graphiques des centres: ${chartsByCategory.centres?.length || 0}`,
            `Total des graphiques: ${availableCharts.length}`,
            `Pages estimées: ${estimatedTotalPages}+`
        ];
        
        const pageWidth = pdf.internal.pageSize.getWidth();
        const boxWidth = pageWidth - (PDF_CONFIG.margins.left + PDF_CONFIG.margins.right);
        
        pdf.setFillColor(...PDF_CONFIG.colors.light);
        pdf.rect(PDF_CONFIG.margins.left, currentY, boxWidth, 40, 'F');
        pdf.setDrawColor(...PDF_CONFIG.colors.primary);
        pdf.setLineWidth(1);
        pdf.rect(PDF_CONFIG.margins.left, currentY, boxWidth, 40, 'S');
        
        pdf.setFontSize(10);
        pdf.setTextColor(...PDF_CONFIG.colors.text);
        
        reportInfo.forEach((info, index) => {
            pdf.text(`• ${info}`, PDF_CONFIG.margins.left + 5, currentY + 10 + (index * 8));
        });
        
        addFooter(pdf, currentPage, estimatedTotalPages);
        
        // Page sommaire
        pdf.addPage();
        currentPage++;
        currentY = addHeader(pdf, 'TABLE DES MATIÈRES', currentPage, false);
        currentY += 10;
        
        pdf.setFontSize(12);
        pdf.setTextColor(...PDF_CONFIG.colors.secondary);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Sommaire du rapport', PDF_CONFIG.margins.left, currentY);
        currentY += 15;
        
        pdf.setFontSize(11);
        pdf.setTextColor(...PDF_CONFIG.colors.primary);
        pdf.setFont('helvetica', 'bold');
        pdf.text('1. Statistiques Globales', PDF_CONFIG.margins.left, currentY);
        pdf.text('Page 3', pageWidth - PDF_CONFIG.margins.right - 20, currentY);
        currentY += 10;
        
        if (chartsByCategory.bénéficiaires?.length > 0) {
            pdf.setTextColor(...PDF_CONFIG.colors.secondary);
            pdf.text('2. Analyses des Bénéficiaires', PDF_CONFIG.margins.left, currentY);
            currentY += 8;
            
            chartsByCategory.bénéficiaires.forEach((chart, index) => {
                const pageNum = `${index + 4}+`;
                pdf.setFontSize(10);
                pdf.setTextColor(...PDF_CONFIG.colors.text);
                pdf.setFont('helvetica', 'normal');
                pdf.text(`   2.${index + 1} ${chart.title}`, PDF_CONFIG.margins.left, currentY);
                pdf.text(`Page ${pageNum}`, pageWidth - PDF_CONFIG.margins.right - 30, currentY);
                currentY += 6;
            });
            currentY += 5;
        }
        
        if (chartsByCategory.centres?.length > 0) {
            pdf.setFontSize(11);
            pdf.setTextColor(...PDF_CONFIG.colors.secondary);
            pdf.setFont('helvetica', 'bold');
            const centresStartPage = 4 + (chartsByCategory.bénéficiaires?.length || 0);
            pdf.text('3. Analyses des Centres', PDF_CONFIG.margins.left, currentY);
            currentY += 8;
            
            chartsByCategory.centres.forEach((chart, index) => {
                const pageNum = `${centresStartPage + index}+`;
                pdf.setFontSize(10);
                pdf.setTextColor(...PDF_CONFIG.colors.text);
                pdf.setFont('helvetica', 'normal');
                pdf.text(`   3.${index + 1} ${chart.title}`, PDF_CONFIG.margins.left, currentY);
                pdf.text(`Page ${pageNum}`, pageWidth - PDF_CONFIG.margins.right - 30, currentY);
                currentY += 6;
            });
        }
        
        addFooter(pdf, currentPage, estimatedTotalPages);
        
        // Page statistiques globales
        pdf.addPage();
        currentPage++;
        currentY = addHeader(pdf, 'STATISTIQUES GLOBALES', currentPage, false);
        currentY += 10;
        
        Object.entries(chartsByCategory).forEach(([category, charts]) => {
            let spaceCheck = ensurePageSpace(pdf, currentY, 60, currentPage, estimatedTotalPages);
            currentY = spaceCheck.currentY;
            currentPage = spaceCheck.pageNumber;
            
            currentY = addSectionTitle(pdf, `Statistiques - ${category.charAt(0).toUpperCase() + category.slice(1)}`, currentY);
            
            const categoryStats = [
                ['Métrique', 'Valeur'],
                ['Nombre de graphiques', charts.length.toString()],
                ['Types de graphiques', [...new Set(charts.map(c => c.type))].length.toString()],
                ['Graphiques en secteurs', charts.filter(c => c.type === 'doughnut').length.toString()],
                ['Graphiques en barres', charts.filter(c => c.type === 'bar').length.toString()],
                ['Graphiques linéaires', charts.filter(c => c.type === 'line').length.toString()]
            ];
            
            const tableResult = addDataTable(pdf, categoryStats[0], categoryStats.slice(1), currentY, {
                pageNumber: currentPage,
                totalPages: estimatedTotalPages
            });
            currentY = tableResult.currentY + 10;
            currentPage = tableResult.pageNumber;
        });
        
        addFooter(pdf, currentPage, estimatedTotalPages);
        
        // Pages des graphiques
        for (let i = 0; i < availableCharts.length; i++) {
            const chartInfo = availableCharts[i];
            
            pdf.addPage();
            currentPage++;
            currentY = addHeader(pdf, `${chartInfo.title} (${chartInfo.category})`, currentPage, false);
            currentY += 10;
            
            const chartImage = optimizeChartImage(chartInfo.canvas);
            const availableWidth = pageWidth - (PDF_CONFIG.margins.left + PDF_CONFIG.margins.right);
            const chartWidth = availableWidth * 0.85;
            const aspectRatio = chartInfo.canvas.height / chartInfo.canvas.width;
            let chartHeight = chartWidth * aspectRatio;
            
            const maxChartHeight = 80;
            if (chartHeight > maxChartHeight) {
                chartHeight = maxChartHeight;
            }
            
            const chartX = (pageWidth - chartWidth) / 2;
            
            let spaceCheck = ensurePageSpace(pdf, currentY, chartHeight + 20, currentPage, estimatedTotalPages);
            currentY = spaceCheck.currentY;
            currentPage = spaceCheck.pageNumber;
            
            pdf.setDrawColor(...PDF_CONFIG.colors.light);
            pdf.setLineWidth(1);
            pdf.rect(chartX - 5, currentY - 5, chartWidth + 10, chartHeight + 10, 'S');
            
            pdf.addImage(chartImage, 'JPEG', chartX, currentY, chartWidth, chartHeight);
            currentY += chartHeight + 20;
            
            let stats;
            try {
                switch (chartInfo.type) {
                    case 'doughnut':
                    case 'pie':
                        stats = generateDoughnutStats(chartInfo.chart);
                        break;
                    case 'bar':
                        stats = generateBarStats(chartInfo.chart);
                        break;
                    case 'line':
                        stats = generateLineStats(chartInfo.chart);
                        break;
                    default:
                        stats = { type: 'unknown', message: 'Type de graphique non reconnu' };
                }
                
                if (stats.type !== 'unknown') {
                    const statsResult = addChartStats(pdf, stats, currentY, {
                        pageNumber: currentPage,
                        totalPages: estimatedTotalPages
                    });
                    currentY = statsResult.currentY;
                    currentPage = statsResult.pageNumber;
                }
            } catch (error) {
                spaceCheck = ensurePageSpace(pdf, currentY, 15, currentPage, estimatedTotalPages);
                currentY = spaceCheck.currentY;
                currentPage = spaceCheck.pageNumber;
                
                pdf.setFontSize(10);
                pdf.setTextColor(...PDF_CONFIG.colors.primary);
                pdf.text('Statistiques non disponibles pour ce graphique', 
                        PDF_CONFIG.margins.left, currentY);
                currentY += 10;
            }
            
            addFooter(pdf, currentPage, estimatedTotalPages);
        }
        
        const finalTotalPages = currentPage;
        
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        const fileName = `rapport_complet_beneficiaires_centres_${timestamp}.pdf`;
        pdf.save(fileName);
        
        showSuccessMessage(`Rapport exporté: ${fileName} - ${availableCharts.length} graphiques, ${finalTotalPages} pages`);
        
    } catch (error) {
        showErrorMessage(`Erreur exportation: ${error.message}`);
    }
}


// Messages d'état
function showSuccessMessage(message) {
    const notification = document.createElement('div');
    notification.className = 'fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 max-w-md';
    notification.innerHTML = `<div class="flex items-start"><span class="text-sm leading-relaxed">${message}</span></div>`;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (document.body.contains(notification)) {
            document.body.removeChild(notification);
        }
    }, 6000);
}

function showErrorMessage(message) {
    const notification = document.createElement('div');
    notification.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 max-w-md';
    notification.innerHTML = `<div class="flex items-start"><span class="text-sm leading-relaxed">${message}</span></div>`;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (document.body.contains(notification)) {
            document.body.removeChild(notification);
        }
    }, 7000);
}

// Créer le bouton d'exportation avec icône PDF
function createExportButton() {
    const existingButton = document.getElementById('export-all-charts-btn');
    if (existingButton) {
        return;
    }
    
    const exportButton = document.createElement('button');
    exportButton.id = 'export-all-charts-btn';
    exportButton.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20M12,19L8,15H10.5V12H13.5V15H16L12,19Z"/>
        </svg>
    `;
    exportButton.title = "Exporter le rapport en PDF";
    exportButton.onclick = exportAllChartsToPDF;
    
    document.body.appendChild(exportButton);
}


// Chargement de jsPDF
function loadjsPDF() {
    return new Promise((resolve, reject) => {
        if (window.jspdf) {
            resolve();
            return;
        }
        
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// Initialisation
function initializePDFExport() {
    loadjsPDF().then(() => {
        const style = document.createElement('style');
        style.textContent = `
            .export-btn {
                background: #a554b7;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s ease;
                font-size: 13px;
                font-weight: 500;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                font-family: system-ui, -apple-system, sans-serif;
                white-space: nowrap;
            }
            .export-btn:hover {
                background: #8e45a0;
            }
            .export-btn:active {
                background: #7a3a8a;
            }
        `;
        document.head.appendChild(style);
        
        createExportButton();
        
    }).catch(() => {
        showErrorMessage('Impossible de charger le système d\'exportation PDF');
    });
}

// Initialisation automatique
window.addEventListener('load', () => {
    setTimeout(() => {
        initializePDFExport();
    }, 1000);
});

// Export des fonctions
window.exportAllChartsToPDF = exportAllChartsToPDF;
window.exportChartToPDF = exportChartToPDF;