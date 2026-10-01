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

    const charts = [chart];

    const budgetDataEl = document.getElementById('budgetChartData');
    if (budgetDataEl) {
        [buildBudgetAccountChart(budgetDataEl), buildBudgetTrendChart(budgetDataEl)]
            .filter(Boolean)
            .forEach((item) => charts.push(item));
    }

    new MutationObserver(() => {
        const isLight = document.documentElement.classList.contains('theme-light');
        const textColor = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim();
        const gridColor = isLight ? 'rgba(15, 23, 42, 0.08)' : 'rgba(255, 255, 255, 0.08)';
        charts.forEach((item) => {
            const legend = item.options.plugins && item.options.plugins.legend;
            if (legend && legend.labels) legend.labels.color = textColor;
            Object.values(item.options.scales || {}).forEach((scale) => {
                if (scale.ticks) scale.ticks.color = textColor;
                if (scale.grid) scale.grid.color = gridColor;
            });
            item.update('none');
        });
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
})();

function themeColors() {
    const isLight = document.documentElement.classList.contains('theme-light');
    return {
        text: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim(),
        grid: isLight ? 'rgba(15, 23, 42, 0.08)' : 'rgba(255, 255, 255, 0.08)'
    };
}

function currencyTick(value) {
    return 'MWK ' + Number(value).toLocaleString();
}

function baseOptions(colors, percentAxis) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
                labels: {
                    color: colors.text,
                    font: { family: 'Outfit', size: 12 }
                }
            }
        },
        scales: {
            x: {
                grid: { color: colors.grid },
                ticks: { color: colors.text, font: { family: 'Outfit' } }
            },
            y: {
                grid: { color: colors.grid },
                ticks: {
                    color: colors.text,
                    font: { family: 'Outfit' },
                    callback: percentAxis
                        ? function (value) { return value + '%'; }
                        : currencyTick
                }
            }
        }
    };
}

function buildBudgetAccountChart(data) {
    const ctx = document.getElementById('budgetAccountChart');
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.accountLabels,
            datasets: [
                {
                    label: 'Budget',
                    data: data.accountBudget,
                    backgroundColor: 'rgba(139, 92, 246, 0.6)',
                    borderRadius: 6
                },
                {
                    label: 'Actual',
                    data: data.accountActual,
                    backgroundColor: 'rgba(239, 68, 68, 0.6)',
                    borderRadius: 6
                }
            ]
        },
        options: baseOptions(themeColors(), false)
    });
}

function buildBudgetTrendChart(data) {
    const ctx = document.getElementById('budgetTrendChart');
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.monthLabels,
            datasets: [
                {
                    label: 'Budget Utilization (%)',
                    data: data.monthUtilization,
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34, 197, 94, 0.15)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    spanGaps: true
                }
            ]
        },
        options: baseOptions(themeColors(), true)
    });
}
