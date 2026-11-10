(() => {
    "use strict";
    const dialog = document.querySelector("[data-slip-dialog]");
    if (!dialog) return;

    const image = dialog.querySelector("[data-slip-dialog-image]");
    const title = dialog.querySelector("[data-slip-dialog-title]");
    const original = dialog.querySelector("[data-slip-dialog-original]");

    document.querySelectorAll("[data-slip-preview]").forEach((button) => {
        button.addEventListener("click", () => {
            const url = button.dataset.slipUrl || "";
            const label = button.dataset.slipTitle || "ดูสลิป";
            image.src = url;
            image.alt = label;
            title.textContent = label;
            original.href = url;
            dialog.showModal();
        });
    });

    dialog.querySelectorAll("[data-slip-dialog-close]").forEach((button) => {
        button.addEventListener("click", () => dialog.close());
    });
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener("close", () => {
        image.removeAttribute("src");
        original.removeAttribute("href");
    });
})();
