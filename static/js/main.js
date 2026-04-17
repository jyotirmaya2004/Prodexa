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
// Dashboard fake chart animation
// -----------------------------
const chartBox = document.querySelector(".chart-placeholder");

if (chartBox) {
    let dots = 0;

    setInterval(() => {
        dots = (dots + 1) % 4;
        chartBox.innerText = "Loading Analytics" + ".".repeat(dots);
    }, 500);
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
        backBtn.style.cssText = "margin: 20px 0 20px 20px; padding: 8px 16px; background-color: #f3f4f6; color: #374151; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; font-weight: 500; font-family: inherit; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; box-shadow: 0 1px 2px rgba(0,0,0,0.05);";

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