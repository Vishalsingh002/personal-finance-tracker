document.addEventListener("DOMContentLoaded", function () {
  fetch("/api/dashboard-charts")
    .then((response) => response.json())
    .then((data) => {
      // 1. Monthly Trends Chart
      const trendCtx = document.getElementById("trendChart");
      if (trendCtx) {
        new Chart(trendCtx, {
          type: "bar",
          data: {
            labels: data.trends.labels,
            datasets: [
              {
                label: "Income (₹)",
                data: data.trends.income,
                backgroundColor: "rgba(40, 167, 69, 0.7)",
                borderColor: "#28a745",
                borderWidth: 1,
                borderRadius: 5,
              },
              {
                label: "Expenses (₹)",
                data: data.trends.expenses,
                backgroundColor: "rgba(220, 53, 69, 0.7)",
                borderColor: "#dc3545",
                borderWidth: 1,
                borderRadius: 5,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              y: {
                beginAtZero: true,
                ticks: {
                  callback: function (value) {
                    return "₹" + value.toLocaleString("en-IN");
                  },
                },
              },
            },
            plugins: {
              tooltip: {
                callbacks: {
                  label: function (context) {
                    return (
                      context.dataset.label +
                      ": ₹" +
                      context.parsed.y.toLocaleString("en-IN")
                    );
                  },
                },
              },
            },
          },
        });
      }

      // 2. Category Doughnut Chart
      const catCtx = document.getElementById("categoryChart");
      if (catCtx) {
        if (data.categories.labels.length === 0) {
          catCtx.parentElement.innerHTML =
            '<div class="text-center text-muted py-5"><i class="fas fa-chart-pie fs-1 mb-2"></i><p>No expenses recorded this month.</p></div>';
        } else {
          new Chart(catCtx, {
            type: "doughnut",
            data: {
              labels: data.categories.labels,
              datasets: [
                {
                  data: data.categories.data,
                  backgroundColor: [
                    "#4e73df",
                    "#1cc88a",
                    "#36b9cc",
                    "#f6c23e",
                    "#e74a3b",
                    "#6f42c1",
                    "#fd7e14",
                    "#20c997",
                    "#6c757d",
                    "#e83e8c",
                  ],
                },
              ],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { position: "bottom" },
                tooltip: {
                  callbacks: {
                    label: function (context) {
                      const val = context.parsed || 0;
                      return (
                        context.label + ": ₹" + val.toLocaleString("en-IN")
                      );
                    },
                  },
                },
              },
            },
          });
        }
      }
    })
    .catch((err) => console.error("Error loading dashboard charts:", err));
});