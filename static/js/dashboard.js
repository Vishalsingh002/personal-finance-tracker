document.addEventListener("DOMContentLoaded", function () {
    fetch("/api/chart-data")
        .then(res => res.json())
        .then(data => {
            const ctxCash = document.getElementById("cashFlowChart");
            if (ctxCash) {
                new Chart(ctxCash, {
                    type: "bar",
                    data: {
                        labels: data.monthly.labels,
                        datasets: [
                            { label: "Income ($)", data: data.monthly.income, backgroundColor: "rgba(25, 135, 84, 0.75)" },
                            { label: "Expenses ($)", data: data.monthly.expenses, backgroundColor: "rgba(220, 53, 69, 0.75)" }
                        ]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }

            const ctxCat = document.getElementById("categoryChart");
            if (ctxCat && data.categories.labels.length > 0) {
                new Chart(ctxCat, {
                    type: "doughnut",
                    data: {
                        labels: data.categories.labels,
                        datasets: [{
                            data: data.categories.data,
                            backgroundColor: ["#fd7e14", "#0d6efd", "#6f42c1", "#d63384", "#20c997", "#ffc107", "#0dcaf0", "#6c757d"]
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }
        });
});