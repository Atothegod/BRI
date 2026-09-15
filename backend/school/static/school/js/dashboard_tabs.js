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

    const activate = (key) => {
        const input = inputs.get(key) || inputs.values().next().value;
        if (!input) {
            return;
        }

        input.checked = true;
        labels.forEach((label) => {
            const isActive = label.dataset.tabLabel === input.dataset.tabInput;
            label.classList.toggle("is-active", isActive);
            label.setAttribute("aria-selected", isActive ? "true" : "false");
        });
    };

    const syncFromHash = () => {
        const key = window.location.hash.replace("#", "");
        activate(inputs.has(key) ? key : "students");
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
            }
        });
    });

    window.addEventListener("hashchange", syncFromHash);
    syncFromHash();
})();
