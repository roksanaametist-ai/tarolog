(function () {
    "use strict";

    const config = window.FRENSY_CONFIG || {};
    const portal = document.getElementById("portal");
    const hero = document.getElementById("hero");
    const form = document.getElementById("lead-form");
    const formError = document.getElementById("form-error");
    const burnOverlay = document.getElementById("burn-overlay");
    const afterBurn = document.getElementById("after-burn");
    const btnRebirth = document.getElementById("btn-rebirth");
    const botLinkAfter = document.getElementById("bot-link-after");

    /* —— Particles —— */
    function initParticles() {
        const canvas = document.getElementById("particles");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        let w, h, particles;

        function resize() {
            w = canvas.width = window.innerWidth;
            h = canvas.height = window.innerHeight;
        }

        function create() {
            const count = Math.min(120, Math.floor((w * h) / 12000));
            particles = Array.from({ length: count }, () => ({
                x: Math.random() * w,
                y: Math.random() * h,
                r: Math.random() * 1.5 + 0.3,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3,
                a: Math.random() * 0.5 + 0.2,
            }));
        }

        function draw() {
            ctx.clearRect(0, 0, w, h);
            for (const p of particles) {
                p.x += p.vx;
                p.y += p.vy;
                if (p.x < 0) p.x = w;
                if (p.x > w) p.x = 0;
                if (p.y < 0) p.y = h;
                if (p.y > h) p.y = 0;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(125, 249, 255, ${p.a})`;
                ctx.fill();
            }
            requestAnimationFrame(draw);
        }

        resize();
        create();
        draw();
        window.addEventListener("resize", () => {
            resize();
            create();
        });
    }

    /* —— Scroll reveal —— */
    function initReveal() {
        const els = document.querySelectorAll(".reveal");
        const obs = new IntersectionObserver(
            (entries) => {
                entries.forEach((e) => {
                    if (e.isIntersecting) {
                        e.target.classList.add("visible");
                    }
                });
            },
            { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
        );
        els.forEach((el) => obs.observe(el));
    }

    /* —— Hero entrance —— */
    function playHeroEntrance() {
        hero.classList.add("entered");
        const content = hero.querySelector(".hero-content");
        if (content) {
            requestAnimationFrame(() => content.classList.add("visible"));
        }
    }

    /* —— Burn transition —— */
    function runBurnTransition(onDone) {
        burnOverlay.hidden = false;
        burnOverlay.setAttribute("aria-hidden", "false");
        burnOverlay.classList.add("active");

        requestAnimationFrame(() => {
            burnOverlay.classList.add("burning");
        });

        setTimeout(() => {
            burnOverlay.classList.remove("active", "burning");
            burnOverlay.hidden = true;
            burnOverlay.setAttribute("aria-hidden", "true");
            onDone();
        }, 3200);
    }

    function showAfterBurn(botUrl) {
        portal.classList.add("hidden-cycle");
        afterBurn.hidden = false;
        if (botUrl && botLinkAfter) {
            botLinkAfter.href = botUrl;
        }
        window.scrollTo(0, 0);
    }

    function hideAfterBurn() {
        afterBurn.hidden = true;
        portal.classList.remove("hidden-cycle");
    }

    /* —— Lead form —— */
    async function handleSubmit(e) {
        e.preventDefault();
        formError.hidden = true;

        const fd = new FormData(form);
        const name = (fd.get("name") || "").toString().trim();
        const contact = (fd.get("contact") || "").toString().trim();
        const consent_pd = fd.get("consent_pd") === "1";
        const consent_tb = fd.get("consent_tb") === "1";
        const consent_oferta = fd.get("consent_oferta") === "1";
        if (!consent_pd || !consent_tb || !consent_oferta) {
            formError.textContent = "Нужны три отдельные отметки: обработка данных, трансграничная передача и оферта.";
            formError.hidden = false;
            return;
        }

        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;

        try {
            const res = await fetch("/api/lead", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, contact, consent_pd: true, consent_tb: true, consent_oferta: true }),
            });
            const data = await res.json();

            if (!res.ok || !data.ok) {
                formError.textContent = data.error || "Не удалось отправить. Попробуйте ещё раз.";
                formError.hidden = false;
                submitBtn.disabled = false;
                return;
            }

            const botUrl = data.bot_url || config.botUrl;

            runBurnTransition(() => {
                showAfterBurn(botUrl);
                if (botUrl) {
                    window.open(botUrl, "_blank", "noopener,noreferrer");
                }
            });
        } catch {
            formError.textContent = "Ошибка сети. Проверьте подключение.";
            formError.hidden = false;
            submitBtn.disabled = false;
        }
    }

    /* —— Pererождение —— */
    function handleRebirth() {
        hideAfterBurn();
        if (form) {
            form.reset();
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.disabled = false;
        }
        if (formError) formError.hidden = true;
        document.querySelectorAll(".reveal").forEach((el) => {
            el.classList.remove("visible");
        });
        hero.classList.remove("entered");
        const content = hero.querySelector(".hero-content");
        if (content) content.classList.remove("visible");

        window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });

        requestAnimationFrame(() => {
            playHeroEntrance();
            initReveal();
            document.querySelectorAll(".reveal").forEach((el) => {
                const rect = el.getBoundingClientRect();
                if (rect.top < window.innerHeight * 0.9) {
                    el.classList.add("visible");
                }
            });
        });
    }

    /* —— Smooth CTA scroll —— */
    document.querySelectorAll('a[href^="#"]').forEach((a) => {
        a.addEventListener("click", (ev) => {
            const id = a.getAttribute("href");
            if (!id || id === "#") return;
            const target = document.querySelector(id);
            if (target) {
                ev.preventDefault();
                target.scrollIntoView({ behavior: "smooth" });
            }
        });
    });

    initParticles();
    initReveal();
    playHeroEntrance();

    if (form) form.addEventListener("submit", handleSubmit);
    if (btnRebirth) btnRebirth.addEventListener("click", handleRebirth);
})();
