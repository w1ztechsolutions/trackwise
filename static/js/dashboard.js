(function () {
    const chartDataEl = document.getElementById('chartData');
    if (!chartDataEl) return;

    const chartLabels = chartDataEl.labels;
    const chartSales = chartDataEl.sales;
    const chartExpenses = chartDataEl.expenses;

    const ctx = document.getElementById('salesExpensesChart');
    if (!ctx) return;

    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartLabels,
            datasets: [
                {
                    label: 'Sales Revenue',
                    data: chartSales,
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.15)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Operating Expenses',
                    data: chartExpenses,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.05)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim(),
                        font: {
                            family: 'Outfit',
                            size: 12
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: document.documentElement.classList.contains('theme-light')
                            ? 'rgba(15, 23, 42, 0.08)'
                            : 'rgba(255, 255, 255, 0.08)'
                    },
                    ticks: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim(),
                        font: { family: 'Outfit' }
                    }
                },
                y: {
                    grid: {
                        color: document.documentElement.classList.contains('theme-light')
                            ? 'rgba(15, 23, 42, 0.08)'
                            : 'rgba(255, 255, 255, 0.08)'
                    },
                    ticks: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim(),
                        font: { family: 'Outfit' },
                        callback: function(value) {
                            return 'MWK ' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });

    new MutationObserver(() => {
        const isLight = document.documentElement.classList.contains('theme-light');
        const textColor = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim();
        const gridColor = isLight ? 'rgba(15, 23, 42, 0.08)' : 'rgba(255, 255, 255, 0.08)';
        chart.options.plugins.legend.labels.color = textColor;
        chart.options.scales.x.ticks.color = textColor;
        chart.options.scales.y.ticks.color = textColor;
        chart.options.scales.x.grid.color = gridColor;
        chart.options.scales.y.grid.color = gridColor;
        chart.update('none');
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
})();
