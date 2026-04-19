function showToast(message, type) {
    const toast = document.createElement("div");
    const palette = {
        success: "#16a34a",
        error: "#dc2626",
        info: "#0284c7",
    };

    toast.textContent = message;
    toast.style.position = "fixed";
    toast.style.right = "20px";
    toast.style.bottom = "20px";
    toast.style.zIndex = "1100";
    toast.style.background = palette[type] || palette.info;
    toast.style.color = "white";
    toast.style.padding = "10px 14px";
    toast.style.borderRadius = "12px";
    toast.style.boxShadow = "0 12px 30px rgba(2,6,23,0.2)";
    toast.style.fontWeight = "600";

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2200);
}

function initRevealOnScroll() {
    const revealEls = document.querySelectorAll(".reveal");
    if (!revealEls.length) {
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("revealed");
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    revealEls.forEach((el) => observer.observe(el));
}

function initCardTilt() {
    const cards = document.querySelectorAll("[data-tilt]");
    cards.forEach((card) => {
        card.addEventListener("mousemove", (event) => {
            const rect = card.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;
            const rotateX = ((y / rect.height) - 0.5) * -8;
            const rotateY = ((x / rect.width) - 0.5) * 8;
            card.style.transform = `perspective(800px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-6px)`;
        });

        card.addEventListener("mouseleave", () => {
            card.style.transform = "";
        });
    });
}

function initParticleBackground() {
    const canvas = document.getElementById("bg-particles");
    if (!canvas) {
        return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) {
        return;
    }

    let particles = [];

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        particles = Array.from({ length: Math.max(24, Math.floor(window.innerWidth / 60)) }, () => ({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.4,
            vy: (Math.random() - 0.5) * 0.4,
            radius: Math.random() * 1.8 + 0.7,
        }));
    }

    function tick() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "rgba(2, 132, 199, 0.35)";

        for (const p of particles) {
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
            if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fill();
        }

        requestAnimationFrame(tick);
    }

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
    tick();
}

function initSearchFormEffects() {
    document.querySelectorAll("form").forEach((form) => {
        form.addEventListener("submit", function () {
            const button = form.querySelector("button[type='submit']");
            if (button) {
                button.innerText = "Searching...";
                button.disabled = true;
            }
        });
    });

    const searchInput = document.querySelector("input[name='product']");
    if (searchInput) {
        searchInput.addEventListener("input", function () {
            if (this.value.trim().length < 2) {
                this.classList.add("border-danger");
            } else {
                this.classList.remove("border-danger");
            }
        });
    }
}

function initSaveButtons() {
    document.querySelectorAll(".save-btn").forEach((button) => {
        button.addEventListener("click", async function () {
            const originalText = this.innerText;
            this.innerText = "Saving...";
            this.disabled = true;

            const productData = {
                "Source": this.dataset.source || "",
                "Source URL": this.dataset.sourceUrl || "",
                "Search URL": this.dataset.searchUrl || "",
                "Product Name": this.dataset.name || "",
                "Price": parseInt(this.dataset.price, 10) || 0,
                "Description": this.dataset.description || "",
                "Image": this.dataset.image || "",
                "Link": this.dataset.link || "",
                "Brand": this.dataset.brand || "Unknown",
                "Curated At": new Date().toISOString().slice(0, 19).replace("T", " "),
            };

            try {
                const response = await fetch("/save", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(productData),
                });

                if (response.ok) {
                    this.innerText = "Saved";
                    this.classList.remove("btn-primary");
                    this.classList.add("btn-success");
                    showToast("Product saved successfully", "success");
                    return;
                }

                if (response.status === 401) {
                    window.location.href = "/login";
                    return;
                }
            } catch (error) {
                console.error(error);
            }

            this.innerText = "Save failed";
            showToast("Could not save product", "error");
            this.disabled = false;
            setTimeout(() => {
                this.innerText = originalText;
            }, 1800);
        });
    });
}

function initRemoveButtons() {
    document.querySelectorAll(".remove-btn").forEach((button) => {
        button.addEventListener("click", async function (e) {
            e.preventDefault();
            const productId = this.dataset.id;
            if (productId) {
                const response = await fetch(`/delete/${productId}`, {
                    method: "POST",
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                });
                if (response.status === 401) {
                    window.location.href = "/login";
                    return;
                }
            }

            const card = this.closest(".product-card");
            if (card) {
                card.style.opacity = "0";
                card.style.transform = "scale(0.96)";
                setTimeout(() => card.remove(), 220);
            } else {
                window.location.href = "/saved";
            }
        });
    });
}

function initCompareCounter() {
    const compareCheckboxes = document.querySelectorAll(".compare-check");
    compareCheckboxes.forEach((box) => {
        box.addEventListener("change", () => {
            const compareCount = document.querySelectorAll(".compare-check:checked").length;
            console.log("Products selected:", compareCount);
        });
    });
}

function animateCountUp(element, targetValue, prefix) {
    const duration = 850;
    const start = performance.now();
    const initial = 0;

    function step(now) {
        const progress = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        const value = Math.round(initial + (targetValue - initial) * eased);
        element.textContent = `${prefix}${value.toLocaleString("en-IN")}`;
        if (progress < 1) {
            requestAnimationFrame(step);
        }
    }

    requestAnimationFrame(step);
}

function initCountUps() {
    const counters = document.querySelectorAll("[data-countup]");
    counters.forEach((counter) => {
        const target = parseInt(counter.dataset.countup || "0", 10);
        if (Number.isNaN(target)) {
            return;
        }
        animateCountUp(counter, target, "");
    });
}

function initAnalyticsCharts() {
    const chartBox = document.querySelector(".chart-placeholder");
    if (!chartBox) {
        return;
    }

    chartBox.innerHTML = "<p style='text-align:center; color:#64748b; font-weight:600;'>Loading analytics...</p>";

    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/chart.js";
    script.onload = () => loadAnalytics();
    document.head.appendChild(script);

    async function loadAnalytics() {
        try {
            const response = await fetch("/api/analytics");
            if (!response.ok) {
                throw new Error("Failed to fetch analytics");
            }
            const data = await response.json();

            chartBox.innerHTML = "";
            chartBox.style.display = "grid";
            chartBox.style.gridTemplateColumns = "repeat(auto-fit, minmax(300px, 1fr))";
            chartBox.style.gap = "22px";
            chartBox.style.width = "100%";

            const brandContainer = document.createElement("div");
            const brandCanvas = document.createElement("canvas");
            brandContainer.appendChild(brandCanvas);
            chartBox.appendChild(brandContainer);

            new Chart(brandCanvas, {
                type: "bar",
                data: {
                    labels: Object.keys(data.brands),
                    datasets: [{
                        label: "Avg Price by Brand (Rs)",
                        data: Object.values(data.brands),
                        backgroundColor: "rgba(2, 132, 199, 0.72)",
                        borderColor: "rgba(2, 132, 199, 1)",
                        borderWidth: 1,
                        borderRadius: 8,
                    }],
                },
                options: {
                    responsive: true,
                    plugins: { title: { display: true, text: "Brand Price Comparison" } },
                },
            });

            let historyNames = Object.keys(data.history).filter((name) => data.history[name].prices.length > 1);
            if (historyNames.length === 0) {
                historyNames = Object.keys(data.history).slice(0, 5);
            } else {
                historyNames.sort((a, b) => data.history[b].prices.length - data.history[a].prices.length);
                historyNames = historyNames.slice(0, 5);
            }

            const historyContainer = document.createElement("div");
            const historyCanvas = document.createElement("canvas");
            historyContainer.appendChild(historyCanvas);
            chartBox.appendChild(historyContainer);

            const colors = ["#0284c7", "#f97316", "#16a34a", "#e11d48", "#7c3aed"];
            const datasets = historyNames.map((name, i) => ({
                label: name.length > 25 ? `${name.substring(0, 25)}...` : name,
                data: data.history[name].prices,
                borderColor: colors[i % colors.length],
                backgroundColor: colors[i % colors.length],
                fill: false,
                tension: 0.22,
            }));

            const maxLen = Math.max(...historyNames.map((name) => data.history[name].prices.length), 1);
            const labels = Array.from({ length: maxLen }, (_, i) => `Save #${i + 1}`);

            new Chart(historyCanvas, {
                type: "line",
                data: { labels, datasets },
                options: {
                    responsive: true,
                    plugins: { title: { display: true, text: "Price History (Top Tracked Products)" } },
                },
            });
        } catch (err) {
            console.error(err);
            chartBox.innerHTML = "<p style='text-align:center; color:#dc2626;'>Failed to load analytics data.</p>";
        }
    }
}

function initGlobalBackButton() {
    const path = window.location.pathname;
    const noBackPages = ["/", "/login", "/register", "/dashboard"];

    if (noBackPages.includes(path)) {
        return;
    }

    const backBtn = document.createElement("button");
    backBtn.innerHTML = "← Go Back";
    backBtn.className = "global-back-btn";

    backBtn.onclick = (e) => {
        e.preventDefault();
        if (window.history.length > 1 && document.referrer.includes(window.location.host)) {
            window.history.back();
        } else {
            window.location.href = "/dashboard";
        }
    };

    const container = document.querySelector("main") || document.body;
    container.appendChild(backBtn);
}

document.addEventListener("DOMContentLoaded", () => {
    initParticleBackground();
    initRevealOnScroll();
    initCardTilt();
    initSearchFormEffects();
    initSaveButtons();
    initRemoveButtons();
    initCompareCounter();
    initCountUps();
    initAnalyticsCharts();
    initGlobalBackButton();
});
