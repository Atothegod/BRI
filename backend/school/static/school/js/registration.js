(() => {
    "use strict";

    const app = document.querySelector("[data-registration-app]");
    const form = document.querySelector("[data-registration-form]");

    if (!app || !form) {
        return;
    }

    const panels = Array.from(form.querySelectorAll("[data-form-step]"));
    const stepButtons = Array.from(app.querySelectorAll("[data-step-jump]"));
    const nextButton = form.querySelector("[data-step-next]");
    const backButton = form.querySelector("[data-step-back]");
    const submitButton = form.querySelector("[data-submit-button]");
    const currentStepTexts = Array.from(app.querySelectorAll("[data-current-step]"));
    const progressLabels = Array.from(app.querySelectorAll("[data-progress-label]"));
    const progressBars = Array.from(app.querySelectorAll("[data-progress-bar]"));
    const progressTracks = Array.from(app.querySelectorAll("[data-progress-track]"));
    const sidebar = app.querySelector("[data-app-sidebar]");
    const menuBackdrop = app.querySelector("[data-menu-backdrop]");
    const menuOpenButton = app.querySelector("[data-menu-open]");
    const uploadInput = form.querySelector("[data-upload-input]");
    const fileLabel = form.querySelector("[data-file-label]");
    const totalSteps = panels.length;
    const hasSteps = totalSteps > 0;
    let currentStep = 1;
    let maxVisitedStep = 1;

    const firstErrorPanel = panels.find((panel) => panel.querySelector(".has-error, .errorlist"));
    if (firstErrorPanel) {
        currentStep = Number(firstErrorPanel.dataset.formStep);
        maxVisitedStep = currentStep;
    }

    app.classList.add("is-enhanced", "reveal-enabled");

    const setClientError = (group, message) => {
        if (!group) {
            return;
        }

        group.classList.add("has-error");
        let error = group.querySelector("[data-client-error]");
        if (!error) {
            error = document.createElement("p");
            error.className = "errorlist";
            error.dataset.clientError = "";
            error.setAttribute("role", "alert");
            group.appendChild(error);
        }
        error.textContent = message;
    };

    const clearClientError = (field) => {
        field.classList.remove("is-invalid");
        const group = field.closest(".field-group, .consent-control");
        if (!group) {
            return;
        }

        const error = group.querySelector("[data-client-error]");
        if (error) {
            error.remove();
        }
        if (!group.querySelector(".errorlist")) {
            group.classList.remove("has-error");
        }
    };

    const scrollToPanel = (panel) => {
        const mobileBar = app.querySelector(".mobile-app-bar");
        const mobileBarHeight = mobileBar && getComputedStyle(mobileBar).display !== "none"
            ? mobileBar.getBoundingClientRect().height
            : 0;
        const offset = mobileBarHeight + 16;
        const top = panel.getBoundingClientRect().top + window.scrollY - offset;
        window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    };

    const showStep = (step, options = {}) => {
        if (!hasSteps) {
            return;
        }
        const nextStep = Math.min(Math.max(step, 1), totalSteps);
        currentStep = nextStep;
        maxVisitedStep = Math.max(maxVisitedStep, nextStep);

        panels.forEach((panel) => {
            const isActive = Number(panel.dataset.formStep) === nextStep;
            panel.classList.toggle("is-active", isActive);
            panel.setAttribute("aria-hidden", String(!isActive));
            if (isActive) {
                panel.classList.add("is-visible");
            }
        });

        stepButtons.forEach((button) => {
            const buttonStep = Number(button.dataset.stepJump);
            const isActive = buttonStep === nextStep;
            button.classList.toggle("is-active", isActive);
            button.classList.toggle("is-complete", buttonStep < nextStep);
            button.setAttribute("aria-current", isActive ? "step" : "false");
            button.setAttribute("aria-disabled", String(buttonStep > maxVisitedStep));
        });

        const activePanel = panels[nextStep - 1];
        const label = activePanel ? activePanel.dataset.stepLabel : "";
        const percent = totalSteps > 1
            ? ((nextStep - 1) / (totalSteps - 1)) * 100
            : 100;

        currentStepTexts.forEach((item) => {
            item.textContent = String(nextStep);
        });
        progressLabels.forEach((item) => {
            item.textContent = label;
        });
        progressBars.forEach((item) => {
            item.style.width = `${percent}%`;
        });
        progressTracks.forEach((item) => {
            item.setAttribute("aria-valuenow", String(nextStep));
        });
        if (backButton) backButton.hidden = nextStep === 1;
        if (nextButton) nextButton.hidden = nextStep === totalSteps;
        if (submitButton) submitButton.hidden = nextStep !== totalSteps;

        if (options.scroll !== false && activePanel) {
            scrollToPanel(activePanel);
        }
        if (options.focus && activePanel) {
            const heading = activePanel.querySelector("h3");
            if (heading) {
                heading.setAttribute("tabindex", "-1");
                heading.focus({ preventScroll: true });
            }
        }
    };

    const validatePanel = (panel, interactive = true) => {
        if (!panel) {
            return true;
        }

        const fields = Array.from(
            panel.querySelectorAll("input:not([type='hidden']):not([type='file']), textarea, select")
        ).filter((field) => !field.disabled);
        let firstInvalid = null;

        fields.forEach((field) => {
            if (!field.checkValidity()) {
                field.classList.add("is-invalid");
                const group = field.closest(".field-group, .consent-control");
                setClientError(group, field.validity.typeMismatch ? "รูปแบบข้อมูลไม่ถูกต้อง" : "กรุณากรอกข้อมูลส่วนนี้");
                firstInvalid = firstInvalid || field;
            }
        });

        if (!firstInvalid) {
            return true;
        }

        if (interactive) {
            const target = firstInvalid.closest(".field-group, .consent-control") || firstInvalid;
            target.scrollIntoView({ behavior: "smooth", block: "center" });
            firstInvalid.focus({ preventScroll: true });
        }
        return false;
    };

    const syncBodyLock = () => {
        const menuIsOpen = sidebar && sidebar.classList.contains("is-open");
        document.body.classList.toggle("is-overlay-open", Boolean(menuIsOpen));
    };

    const setMenu = (isOpen) => {
        if (!sidebar || !menuBackdrop || !menuOpenButton) {
            return;
        }
        sidebar.classList.toggle("is-open", isOpen);
        menuBackdrop.hidden = !isOpen;
        menuOpenButton.setAttribute("aria-expanded", String(isOpen));
        syncBodyLock();
        if (isOpen) {
            const closeButton = sidebar.querySelector("[data-menu-close]");
            if (closeButton) closeButton.focus({ preventScroll: true });
        } else {
            menuOpenButton.focus({ preventScroll: true });
        }
    };

    if (hasSteps && nextButton) {
        nextButton.addEventListener("click", () => {
            const activePanel = panels[currentStep - 1];
            if (validatePanel(activePanel)) {
                showStep(currentStep + 1, { focus: true });
            }
        });
    }

    if (hasSteps && backButton) {
        backButton.addEventListener("click", () => showStep(currentStep - 1, { focus: true }));
    }

    stepButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const step = Number(button.dataset.stepJump);
            if (step <= maxVisitedStep) {
                showStep(step, { focus: true });
                if (sidebar && sidebar.classList.contains("is-open")) {
                    setMenu(false);
                }
            }
        });
    });

    form.addEventListener("input", (event) => clearClientError(event.target));
    form.addEventListener("change", (event) => clearClientError(event.target));

    form.addEventListener("submit", (event) => {
        for (const panel of panels) {
            if (!validatePanel(panel, false)) {
                event.preventDefault();
                const invalidStep = Number(panel.dataset.formStep);
                showStep(invalidStep, { focus: false });
                window.setTimeout(() => validatePanel(panel, true), 30);
                return;
            }
        }

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.setAttribute("aria-busy", "true");
            const label = submitButton.querySelector("span");
            if (label) label.textContent = "กำลังส่ง...";
        }
    });

    if (menuOpenButton) menuOpenButton.addEventListener("click", () => setMenu(true));
    if (menuBackdrop) menuBackdrop.addEventListener("click", () => setMenu(false));
    const menuCloseButton = app.querySelector("[data-menu-close]");
    if (menuCloseButton) menuCloseButton.addEventListener("click", () => setMenu(false));

    if (uploadInput && fileLabel) {
        uploadInput.addEventListener("change", () => {
            const file = uploadInput.files && uploadInput.files[0];
            fileLabel.textContent = file ? file.name : "เลือกรูปสลิป";
        });
    }

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") {
            return;
        }
        if (sidebar && sidebar.classList.contains("is-open")) {
            setMenu(false);
        }
    });

    const revealItems = Array.from(app.querySelectorAll("[data-reveal]"));
    if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        const observer = new IntersectionObserver(
            (entries, instance) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        instance.unobserve(entry.target);
                    }
                });
            },
            { rootMargin: "0px 0px -7% 0px", threshold: 0.08 }
        );
        revealItems.forEach((item) => observer.observe(item));
    } else {
        revealItems.forEach((item) => item.classList.add("is-visible"));
    }

    if (hasSteps) {
        showStep(currentStep, { scroll: false });
    }
})();
