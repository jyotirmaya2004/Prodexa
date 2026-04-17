// -----------------------------
// Search button loading effect
// -----------------------------
document.querySelectorAll("form").forEach(form => {
    form.addEventListener("submit", function () {
        const button = form.querySelector("button");
        if (button) {
            button.innerText = "Searching...";
            button.disabled = true;
        }
    });
});


// -----------------------------
// Save button interaction
// -----------------------------
document.querySelectorAll(".save-btn").forEach(button => {
    button.addEventListener("click", async function () {
        const productData = {
            "Source": this.dataset.source || "",
            "Source URL": this.dataset.sourceUrl || "",
            "Search URL": this.dataset.searchUrl || "",
            "Product Name": this.dataset.name || "",
            "Price": parseInt(this.dataset.price) || 0,
            "Description": this.dataset.description || "",
            "Image": this.dataset.image || "",
            "Link": this.dataset.link || "",
            "Brand": this.dataset.brand || "Unknown",
            "Curated At": new Date().toISOString().slice(0, 19).replace('T', ' ')
        };

        const response = await fetch('/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(productData)
        });

        if (response.ok) {
            this.innerText = "Saved ✓";
            this.style.background = "#16a34a";
            this.disabled = true;
        } else if (response.status === 401) {
            window.location.href = '/login';
        }
    });
});


// -----------------------------
// Remove saved product
// -----------------------------
document.querySelectorAll(".remove-btn").forEach(button => {
    button.addEventListener("click", async function (e) {
        e.preventDefault();
        const productId = this.dataset.id;
        if (productId) {
            const response = await fetch(`/delete/${productId}`, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }
        }
        const card = this.closest(".product-card");
        if (card) {
            card.remove();
        } else {
            window.location.href = '/saved';
        }
    });
});


// -----------------------------
// Compare checkbox counter
// -----------------------------
const compareCheckboxes = document.querySelectorAll(".compare-check");
let compareCount = 0;

compareCheckboxes.forEach(box => {
    box.addEventListener("change", function () {
        compareCount = document.querySelectorAll(".compare-check:checked").length;
        console.log("Products selected:", compareCount);
    });
});


// -----------------------------
// Simple search validation
// -----------------------------
const searchInput = document.querySelector("input[name='product']");

if (searchInput) {
    searchInput.addEventListener("input", function () {
        if (this.value.length < 2) {
            this.style.border = "2px solid red";
        } else {
            this.style.border = "1px solid #ccc";
        }
    });
}


// -----------------------------
// Dashboard Analytics (Chart.js)
// -----------------------------
const chartBox = document.querySelector(".chart-placeholder");

if (chartBox) {
    chartBox.innerHTML = "<p style='text-align:center; color:#6b7280; font-weight: 500;'>Loading Analytics...</p>";

    // Dynamically load Chart.js library
    const script = document.createElement('script');
    script.src = "https://cdn.jsdelivr.net/npm/chart.js";
    script.onload = () => loadAnalytics();
    document.head.appendChild(script);

    async function loadAnalytics() {
        try {
            const response = await fetch('/api/analytics');
            if (!response.ok) throw new Error("Failed to fetch analytics");
            const data = await response.json();

            chartBox.innerHTML = "";
            chartBox.style.display = "grid";
            chartBox.style.gridTemplateColumns = "repeat(auto-fit, minmax(300px, 1fr))";
            chartBox.style.gap = "30px";
            chartBox.style.width = "100%";

            // 1. Brand Price Comparison (Bar Chart)
            const brandContainer = document.createElement("div");
            const brandCanvas = document.createElement("canvas");
            brandContainer.appendChild(brandCanvas);
            chartBox.appendChild(brandContainer);

            new Chart(brandCanvas, {
                type: 'bar',
                data: {
                    labels: Object.keys(data.brands),
                    datasets: [{
                        label: 'Avg Price by Brand (₹)',
                        data: Object.values(data.brands),
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { title: { display: true, text: 'Brand Price Comparison' } }
                }
            });

            // 2. Product Price History (Line Chart)
            let historyNames = Object.keys(data.history).filter(name => data.history[name].prices.length > 1);

            // If no product is saved multiple times yet, just show the top 5 most recent
            if (historyNames.length === 0) {
                historyNames = Object.keys(data.history).slice(0, 5);
            } else {
                historyNames.sort((a, b) => data.history[b].prices.length - data.history[a].prices.length);
                historyNames = historyNames.slice(0, 5); // Limit to top 5 tracked items
            }

            const historyContainer = document.createElement("div");
            const historyCanvas = document.createElement("canvas");
            historyContainer.appendChild(historyCanvas);
            chartBox.appendChild(historyContainer);

            const colors = ['#ef4444', '#10b981', '#f59e0b', '#6366f1', '#ec4899'];
            const datasets = historyNames.map((name, i) => {
                const shortName = name.length > 25 ? name.substring(0, 25) + '...' : name;
                return {
                    label: shortName,
                    data: data.history[name].prices,
                    borderColor: colors[i % colors.length],
                    backgroundColor: colors[i % colors.length],
                    fill: false,
                    tension: 0.1
                };
            });

            let maxLen = Math.max(...historyNames.map(name => data.history[name].prices.length), 1);
            const labels = Array.from({length: maxLen}, (_, i) => `Save #${i + 1}`);

            new Chart(historyCanvas, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    plugins: { title: { display: true, text: 'Price History (Top Tracked Products)' } }
                }
            });

        } catch (err) {
            console.error(err);
            chartBox.innerHTML = "<p style='text-align:center; color:#ef4444;'>Failed to load analytics data.</p>";
        }
    }
}


// -----------------------------
// Global Back Navigation Button
// -----------------------------
document.addEventListener("DOMContentLoaded", () => {
    const path = window.location.pathname;
    const noBackPages = ["/", "/login", "/register", "/dashboard"];

    if (!noBackPages.includes(path)) {
        const backBtn = document.createElement("button");
        backBtn.innerHTML = "← Go Back";
        backBtn.className = "global-back-btn";
        backBtn.style.cssText = "position: fixed; bottom: 30px; left: 30px; z-index: 1000; padding: 10px 20px; background-color: #f3f4f6; color: #374151; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; font-weight: 500; font-family: inherit; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; box-shadow: 0 4px 6px rgba(0,0,0,0.1);";

        backBtn.onmouseover = () => backBtn.style.backgroundColor = "#e5e7eb";
        backBtn.onmouseout = () => backBtn.style.backgroundColor = "#f3f4f6";

        backBtn.onclick = (e) => {
            e.preventDefault();
            if (window.history.length > 1 && document.referrer.includes(window.location.host)) {
                window.history.back();
            } else {
                window.location.href = '/dashboard';
            }
        };

        const container = document.querySelector(".container") || document.querySelector("main") || document.body;
        container.insertBefore(backBtn, container.firstChild);
    }
});