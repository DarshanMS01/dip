/* ==========================================================================
   ClickMart storefront interactions
   Progressive enhancement only: every control works without JavaScript.
   ========================================================================== */

(function () {
    "use strict";

    const onReady = (callback) => {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback);
        } else {
            callback();
        }
    };

    onReady(function () {
        initializeHeader();
        initializeMobileNav();
        initializeMessages();
        initializeAutoSubmit();
        initializeQuantitySteppers();
        initializeConfirmations();
        initializeCopyButtons();
        initializeImageFallbacks();
        initializeProtectedForms();
    });

    /* ---------------------------------------------------------------- header */

    function initializeHeader() {
        const header = document.getElementById("siteHeader");
        if (!header) return;

        const toggleShadow = () => {
            header.classList.toggle("is-scrolled", window.scrollY > 6);
        };
        toggleShadow();
        window.addEventListener("scroll", toggleShadow, { passive: true });
    }

    /* ------------------------------------------------------------- mobile nav */

    function initializeMobileNav() {
        const nav = document.getElementById("mobileNav");
        const toggle = document.querySelector("[data-nav-toggle]");
        const close = document.querySelector("[data-nav-close]");
        const backdrop = document.querySelector("[data-nav-backdrop]");
        if (!nav || !toggle) return;

        const setOpen = (open) => {
            nav.classList.toggle("is-open", open);
            nav.setAttribute("aria-hidden", String(!open));
            toggle.setAttribute("aria-expanded", String(open));
            if (backdrop) backdrop.hidden = !open;
            document.body.style.overflow = open ? "hidden" : "";
            if (open && close) close.focus();
            if (!open) toggle.focus();
        };

        toggle.addEventListener("click", () => {
            setOpen(!nav.classList.contains("is-open"));
        });

        if (close) close.addEventListener("click", () => setOpen(false));
        if (backdrop) backdrop.addEventListener("click", () => setOpen(false));

        nav.addEventListener("click", (event) => {
            if (event.target.closest("a")) setOpen(false);
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && nav.classList.contains("is-open")) {
                setOpen(false);
            }
        });

        window.addEventListener("resize", () => {
            if (window.innerWidth > 900 && nav.classList.contains("is-open")) {
                setOpen(false);
            }
        });
    }

    /* -------------------------------------------------------------- messages */

    function initializeMessages() {
        document.querySelectorAll("[data-dismiss-message]").forEach((button) => {
            button.addEventListener("click", () => {
                const message = button.closest(".message");
                if (!message) return;
                message.style.opacity = "0";
                message.style.transform = "translateY(-4px)";
                message.style.transition = "opacity 160ms ease, transform 160ms ease";
                window.setTimeout(() => message.remove(), 180);
            });
        });
    }

    /* ----------------------------------------------------------- auto submit */

    function initializeAutoSubmit() {
        document.querySelectorAll(".js-auto-submit").forEach((select) => {
            select.addEventListener("change", () => {
                const form = select.form;
                if (!form) return;
                if (typeof form.requestSubmit === "function") {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            });
        });
    }

    /* --------------------------------------------------------- quantity input */

    function initializeQuantitySteppers() {
        document.querySelectorAll("[data-qty-stepper]").forEach((stepper) => {
            const input = stepper.querySelector("[data-qty-input]");
            const up = stepper.querySelector("[data-qty-up]");
            const down = stepper.querySelector("[data-qty-down]");
            if (!input) return;

            const clamp = () => {
                const min = Number(input.min || 1);
                const max = Number(input.max || Number.MAX_SAFE_INTEGER);
                let value = Number.parseInt(input.value, 10);
                if (!Number.isFinite(value)) value = min;
                value = Math.min(Math.max(value, min), max);
                input.value = String(value);
                return value;
            };

            if (up) {
                up.addEventListener("click", () => {
                    input.value = String(Number(input.value || 0) + 1);
                    clamp();
                });
            }

            if (down) {
                down.addEventListener("click", () => {
                    input.value = String(Number(input.value || 1) - 1);
                    clamp();
                });
            }

            input.addEventListener("change", clamp);
            input.addEventListener("blur", clamp);
        });
    }

    /* ---------------------------------------------------------- confirmations */

    function initializeConfirmations() {
        document.querySelectorAll("[data-confirm]").forEach((element) => {
            element.addEventListener("click", (event) => {
                const message = element.getAttribute("data-confirm");
                if (message && !window.confirm(message)) {
                    event.preventDefault();
                    event.stopImmediatePropagation();
                }
            });
        });
    }

    /* ------------------------------------------------------------ copy button */

    function initializeCopyButtons() {
        document.querySelectorAll("[data-copy-target]").forEach((button) => {
            button.addEventListener("click", async () => {
                const target = document.getElementById(button.dataset.copyTarget);
                if (!target) return;
                const text = target.textContent.trim();

                try {
                    if (navigator.clipboard && window.isSecureContext) {
                        await navigator.clipboard.writeText(text);
                    } else {
                        const area = document.createElement("textarea");
                        area.value = text;
                        area.setAttribute("readonly", "");
                        area.style.position = "fixed";
                        area.style.opacity = "0";
                        document.body.appendChild(area);
                        area.select();
                        document.execCommand("copy");
                        document.body.removeChild(area);
                    }
                    const original = button.textContent;
                    button.textContent = "Copied";
                    window.setTimeout(() => (button.textContent = original), 1400);
                } catch (error) {
                    button.textContent = "Copy failed";
                }
            });
        });
    }

    /* ------------------------------------------------------- image fallbacks */

    function initializeImageFallbacks() {
        document.querySelectorAll("img[data-product-image]").forEach((image) => {
            const hide = () => {
                image.style.display = "none";
            };
            image.addEventListener("error", hide, { once: true });
            if (image.complete && image.naturalWidth === 0) hide();
        });
    }

    /* ------------------------------------------------------- double submits */

    function initializeProtectedForms() {
        document.querySelectorAll("form.checkout-form").forEach((form) => {
            form.addEventListener("submit", () => {
                const buttons = form.querySelectorAll("button[type='submit']");
                window.setTimeout(() => {
                    buttons.forEach((button) => {
                        button.disabled = true;
                        button.dataset.originalText = button.textContent;
                        button.textContent = "Placing order…";
                    });
                }, 0);

                window.setTimeout(() => {
                    buttons.forEach((button) => {
                        if (button.dataset.originalText) {
                            button.textContent = button.dataset.originalText;
                        }
                        button.disabled = false;
                    });
                }, 12000);
            });
        });
    }
})();
