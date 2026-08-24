(function () {
    const chartDataEl = document.getElementById('chartData');
    if (!chartDataEl) return;

    const chartLabels = chartDataEl.labels;
    const chartSales = chartDataEl.sales;
    const chartExpenses = chartDataEl.expenses;

    const ctx = document.getElementById('salesExpensesChart');
    if (!ctx) return;

    new Chart(ctx, {
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
                        color: '#9ca3af',
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
                        color: 'rgba(255, 255, 255, 0.03)'
                    },
                    ticks: {
                        color: '#9ca3af',
                        font: { family: 'Outfit' }
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.03)'
                    },
                    ticks: {
                        color: '#9ca3af',
                        font: { family: 'Outfit' },
                        callback: function(value) {
                            return 'MWK ' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
})();
