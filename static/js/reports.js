document.addEventListener("DOMContentLoaded", function () {
    fetch("/api/chart-data")
        .then(res => res.json())
        .then(data => {
            const ctxComp = document.getElementById("incomeVsExpenseChart");
            if (ctxComp) {
                new Chart(ctxComp, {
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

            const ctxSav = document.getElementById("savingsTrendChart");
            if (ctxSav) {
                new Chart(ctxSav, {
                    type: "line",
                    data: {
                        labels: data.monthly.labels,
                        datasets: [{
                            label: "Monthly Net Savings ($)",
                            data: data.monthly.savings,
                            borderColor: "#0d6efd",
                            backgroundColor: "rgba(13, 110, 253, 0.15)",
                            tension: 0.3,
                            fill: true
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }
        });
});