(() => {
    const tabs = document.querySelector("[data-dashboard-tabs]");
    if (!tabs) {
        return;
    }

    const inputs = new Map(
        Array.from(tabs.querySelectorAll("[data-tab-input]")).map((input) => [
            input.dataset.tabInput,
            input,
        ]),
    );
    const labels = Array.from(tabs.querySelectorAll("[data-tab-label]"));
    const dashboardLinks = Array.from(document.querySelectorAll("[data-dashboard-link]"));
    const defaultTab = tabs.dataset.defaultTab || inputs.keys().next().value;

    const activate = (key) => {
        const input = inputs.get(key) || inputs.get(defaultTab) || inputs.values().next().value;
        if (!input) {
            return;
        }

        input.checked = true;
        labels.forEach((label) => {
            const isActive = label.dataset.tabLabel === input.dataset.tabInput;
            label.classList.toggle("is-active", isActive);
            label.setAttribute("aria-selected", isActive ? "true" : "false");
        });
        dashboardLinks.forEach((link) => {
            const isActive = link.dataset.dashboardLink === input.dataset.tabInput;
            link.classList.toggle("is-active", isActive);
            if (isActive) {
                link.setAttribute("aria-current", "page");
            } else {
                link.removeAttribute("aria-current");
            }
        });
    };

    const updateHash = (key) => {
        if (window.location.hash !== `#${key}`) {
            window.history.replaceState(null, "", `#${key}`);
        }
    };

    const syncFromHash = () => {
        const key = window.location.hash.replace("#", "");
        activate(inputs.has(key) ? key : defaultTab);
    };

    labels.forEach((label) => {
        label.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" && event.key !== " ") {
                return;
            }
            event.preventDefault();
            const input = document.getElementById(label.htmlFor);
            if (input) {
                activate(input.dataset.tabInput);
                updateHash(input.dataset.tabInput);
            }
        });
    });

    inputs.forEach((input, key) => {
        input.addEventListener("change", () => {
            if (!input.checked) return;
            activate(key);
            updateHash(key);
        });
    });

    window.addEventListener("hashchange", syncFromHash);
    syncFromHash();
})();
