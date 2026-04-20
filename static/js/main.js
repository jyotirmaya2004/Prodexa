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
    if (window.matchMedia("(hover: none)").matches) {
        return;
    }

    const cards = document.querySelectorAll("[data-tilt]");
    cards.forEach((card) => {
        card.addEventListener("mouseenter", () => {
            card.style.transition = "transform 0.1s ease-out, background-color 0.3s ease";
        });

        card.addEventListener("mousemove", (event) => {
            const rect = card.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;

            // Very subtle rotation, scaling, and translation
            const rotateX = ((y / rect.height) - 0.5) * -2.5;
            const rotateY = ((x / rect.width) - 0.5) * 2.5;
            card.style.transform = `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-2px) scale(1.01)`;
        });

        card.addEventListener("mouseleave", () => {
            card.style.transition = "transform 0.4s ease-out, background-color 0.3s ease";
            card.style.transform = "";
        });
    });
}

function initSearchPlaceholderAnimation() {
    const input = document.querySelector("input[data-placeholder-rotator]");
    if (!input) {
        return;
    }

    const phrases = (input.dataset.placeholderRotator || "")
        .split("|")
        .map((item) => item.trim())
        .filter(Boolean);

    if (!phrases.length) {
        return;
    }

    let phraseIndex = 0;
    let charIndex = 0;
    let deleting = false;

    const tick = () => {
        if (document.activeElement === input && input.value) {
            setTimeout(tick, 350);
            return;
        }

        const phrase = phrases[phraseIndex];
        if (!deleting) {
            charIndex += 1;
            input.setAttribute("placeholder", `Try: ${phrase.slice(0, charIndex)}`);
            if (charIndex >= phrase.length) {
                deleting = true;
                setTimeout(tick, 1200);
                return;
            }
            setTimeout(tick, 70);
        } else {
            charIndex -= 1;
            input.setAttribute("placeholder", `Try: ${phrase.slice(0, Math.max(0, charIndex))}`);
            if (charIndex <= 0) {
                deleting = false;
                phraseIndex = (phraseIndex + 1) % phrases.length;
                setTimeout(tick, 300);
                return;
            }
            setTimeout(tick, 40);
        }
    };

    tick();
}

function initHeroQuoteRotator() {
    const rotator = document.querySelector("[data-hero-quote-rotator]");
    if (!rotator) {
        return;
    }

    const quotes = (rotator.dataset.quotes || "")
        .split("|")
        .map((quote) => quote.trim())
        .filter(Boolean);

    if (quotes.length < 2) {
        return;
    }

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
        rotator.textContent = quotes[0];
        return;
    }

    let quoteIndex = 0;

    const rotateQuote = () => {
        rotator.classList.add("fade-out");

        setTimeout(() => {
            quoteIndex = (quoteIndex + 1) % quotes.length;
            rotator.textContent = quotes[quoteIndex];
            rotator.classList.remove("fade-out");
        }, 600);
    };

    setInterval(rotateQuote, 3800);
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

function initNewsSlider() {
    const sliders = document.querySelectorAll("[data-auto-slider]");
    if (!sliders.length) {
        return;
    }

    sliders.forEach((slider) => {
        const viewport = slider.querySelector(".slider-viewport");
        const track = slider.querySelector(".slider-track");
        if (!viewport || !track) {
            return;
        }

        const cards = Array.from(track.children);
        if (cards.length < 2) {
            return;
        }

        let timerId = null;

        const getStep = () => {
            const card = cards[0];
            if (!card) return 0;
            const cardStyle = window.getComputedStyle(track);
            const gap = parseFloat(cardStyle.columnGap || cardStyle.gap || "16") || 16;
            return card.getBoundingClientRect().width + gap;
        };

        const advance = () => {
            const step = getStep();
            const maxScroll = viewport.scrollWidth - viewport.clientWidth - 4;
            if (step <= 0) {
                return;
            }

            if (viewport.scrollLeft >= maxScroll) {
                viewport.scrollTo({ left: 0, behavior: "smooth" });
                return;
            }

            viewport.scrollBy({ left: step, behavior: "smooth" });
        };

        const stop = () => {
            if (timerId) {
                window.clearInterval(timerId);
                timerId = null;
            }
        };

        const start = () => {
            stop();
            const interval = parseInt(slider.dataset.sliderInterval || "3200", 10) || 3200;
            timerId = window.setInterval(advance, interval);
        };

        slider.addEventListener("mouseenter", stop);
        slider.addEventListener("mouseleave", start);
        slider.addEventListener("focusin", stop);
        slider.addEventListener("focusout", start);

        start();
    });
}

function initSearchFormEffects() {
    document.querySelectorAll("form").forEach((form) => {
        form.addEventListener("submit", function () {
            const action = form.getAttribute("action");
            if (action && action.includes("/search")) {
                const searchInput = form.querySelector("input[name='product']");
                const query = searchInput ? searchInput.value.trim() : "";
                if (query.length >= 2) {
                    showSkeletonLoading(query);
                }
            }

            const button = form.querySelector("button[type='submit']");
            if (button) {
                button.dataset.originalText = button.innerText;
                let btnText = "Please wait...";
                if (action && action.includes("/search")) btnText = "Searching...";
                else if (action && action.includes("/login")) btnText = "Logging in...";
                else if (action && action.includes("/register")) btnText = "Creating account...";
                else if (action && action.includes("forgot-password")) btnText = "Sending code...";
                else if (action && action.includes("reset-password")) btnText = "Updating password...";
                else if (action && action.includes("review")) btnText = "Submitting review...";

                setTimeout(() => {
                    button.innerText = btnText;
                    button.disabled = true;
                }, 10);
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

function showSkeletonLoading(query) {
    const main = document.querySelector("main");
    if (!main) return;

    const escapeHtml = (unsafe) => {
        return (unsafe || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    };

    const skeletonContainer = document.createElement("div");
    skeletonContainer.id = "skeleton-loading-overlay";
    // Make it a full-screen overlay to prevent layout shifts or blank spaces.
    Object.assign(skeletonContainer.style, {
        position: 'fixed',
        top: '0',
        left: '0',
        width: '100vw',
        height: '100vh',
        backgroundColor: 'white',
        zIndex: '40', // Lower than nav (z-50) so the navbar stays visible
        overflowY: 'auto',
    });

    // Generate 8 animated placeholder cards matching your UI
    const cardsHtml = Array(8).fill(0).map(() => `
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden animate-pulse flex flex-col h-full">
            <div class="h-48 bg-gray-200 w-full"></div>
            <div class="p-5 flex-grow flex flex-col">
                <div class="h-4 bg-gray-200 rounded w-1/3 mb-3"></div>
                <div class="h-6 bg-gray-200 rounded w-full mb-2"></div>
                <div class="h-6 bg-gray-200 rounded w-2/3 mb-4"></div>
                <div class="h-8 bg-gray-200 rounded w-2/5 mb-4"></div>
                <div class="h-4 bg-gray-200 rounded w-full mb-2"></div>
                <div class="h-4 bg-gray-200 rounded w-4/5 mb-4"></div>
                <div class="mt-auto pt-4 flex gap-2">
                    <div class="h-10 bg-gray-200 rounded w-full"></div>
                    <div class="h-10 bg-gray-200 rounded w-1/4"></div>
                </div>
            </div>
        </div>
    `).join("");

    skeletonContainer.innerHTML = `
        <div class="max-w-7xl mx-auto px-4 py-8 w-full" style="padding-top: 8rem;">
            <div class="mb-8">
                <h1 class="text-3xl font-bold text-gray-900 mb-2">Searching for "${escapeHtml(query)}"...</h1>
                <p class="text-gray-600 flex items-center gap-2">
                    <svg class="animate-spin h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Gathering the best prices from multiple stores. This might take a few seconds...
                </p>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                ${cardsHtml}
            </div>
        </div>
    `;
    document.body.appendChild(skeletonContainer);
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function initSearchSuggestions() {
    const form = document.querySelector("form[action='/search']");
    const searchInput = document.querySelector("input[name='product']");
    const suggestionChips = document.querySelectorAll(".search-suggestion-chip");

    if (!form || !searchInput || !suggestionChips.length) {
        return;
    }

    suggestionChips.forEach((chip) => {
        chip.addEventListener("click", () => {
            const query = (chip.dataset.query || chip.textContent || "").trim();
            if (!query) {
                return;
            }

            searchInput.value = query;
            searchInput.dispatchEvent(new Event("input", { bubbles: true }));
            if (typeof form.requestSubmit === "function") {
                form.requestSubmit();
            } else {
                form.submit();
            }
        });
    });
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
        const initialPath = window.location.pathname;
        const hasHistory = window.history.length > 1;

        if (!hasHistory) {
            window.location.href = "/dashboard";
            return;
        }

        window.history.back();

        setTimeout(() => {
            if (window.location.pathname === initialPath) {
                window.location.href = "/dashboard";
            }
        }, 450);
    };

    const container = document.querySelector("main") || document.body;
    container.appendChild(backBtn);
}

function initAntiInspect() {
    // Disable right-click context menu
    document.addEventListener("contextmenu", (e) => e.preventDefault());

    // Disable F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C, and Ctrl+U
    document.addEventListener("keydown", (e) => {
        if (e.key === "F12" ||
            (e.ctrlKey && e.shiftKey && ["I", "i", "J", "j", "C", "c"].includes(e.key)) ||
            (e.ctrlKey && ["U", "u"].includes(e.key))) {
            e.preventDefault();
        }
    });
}

function initGSAPAnimations() {
    if (typeof gsap === 'undefined') return;

    // Register ScrollTrigger if loaded
    if (typeof ScrollTrigger !== 'undefined') {
        gsap.registerPlugin(ScrollTrigger);

        // Animate reveal elements (overrides default IntersectionObserver logic for GSAP flair)
        gsap.utils.toArray('.reveal').forEach((elem) => {
            elem.classList.remove('revealed'); // Let GSAP handle the styling natively
            gsap.fromTo(elem,
                { y: 50, opacity: 0 },
                {
                    scrollTrigger: {
                        trigger: elem,
                        start: "top 85%",
                    },
                    y: 0,
                    opacity: 1,
                    duration: 0.8,
                    ease: "power3.out"
                }
            );
        });
    }

    // Entry Animations for the hero/search area
    const tl = gsap.timeline();
    tl.from("h1", { duration: 0.8, y: 30, opacity: 0, ease: "back.out(1.2)", delay: 0.2 })
      .from("p.text-lg", { duration: 0.6, y: 20, opacity: 0, ease: "power2.out" }, "-=0.4")
      .from("form[action='/search']", { duration: 0.7, scale: 0.95, opacity: 0, ease: "power3.out" }, "-=0.3");

    // Stagger in product cards dynamically
    gsap.from(".product-card", {
        duration: 0.6,
        y: 40,
        opacity: 0,
        stagger: 0.1,
        ease: "power2.out",
        delay: 0.1
    });
}

function initReviewSlider() {
    const track = document.querySelector(".review-slider-track");
    if (!track || typeof gsap === 'undefined') return;

    // Clone the review items to create a seamless infinite scrolling marquee
    const items = Array.from(track.children);
    items.forEach((item) => {
        const clone = item.cloneNode(true);
        clone.setAttribute("aria-hidden", "true");
        track.appendChild(clone);
    });

    setTimeout(() => {
        const moveDistance = track.scrollWidth / 2;
        const tween = gsap.to(track, {
            x: -moveDistance,
            ease: "none",
            duration: 35,
            repeat: -1
        });

        // Pause sliding on hover so users can read the reviews comfortably
        track.addEventListener("mouseenter", () => tween.pause());
        track.addEventListener("mouseleave", () => tween.play());
    }, 150);
}

function initCaptchaRefresh() {
    const captchaImages = document.querySelectorAll('.captcha-img');
    captchaImages.forEach((img) => {
        img.addEventListener('click', async () => {
            try {
                const response = await fetch('/refresh-captcha');
                if (response.ok) {
                    const data = await response.json();
                    if (data.captcha_prompt) {
                        img.src = data.captcha_prompt;
                    }
                }
            } catch (error) {
                console.error('Error refreshing CAPTCHA:', error);
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initParticleBackground();
    initRevealOnScroll();
    initCardTilt();
    initHeroQuoteRotator();
    initSearchFormEffects();
    initSearchPlaceholderAnimation();
    initSearchSuggestions();
    initSaveButtons();
    initRemoveButtons();
    initCompareCounter();
    initCountUps();
    initAnalyticsCharts();
    initGlobalBackButton();
    initNewsSlider();
    initAntiInspect();

    initGSAPAnimations();
    initReviewSlider();
    initCaptchaRefresh();
});

// Prevent "Back-Forward Cache" issues by removing the skeleton if the user clicks the browser Back button
window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
        document.querySelectorAll("form button[type='submit']").forEach(btn => {
            btn.disabled = false;
            if (btn.dataset.originalText) btn.innerText = btn.dataset.originalText;
        });
        // When navigating back, simply remove the skeleton overlay if it exists.
        const skeleton = document.getElementById("skeleton-loading-overlay");
        if (skeleton) skeleton.remove();
    }
});
