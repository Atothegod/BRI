(() => {
    "use strict";
    const input = document.querySelector("input[name='nickname']");
    const preview = document.querySelector("[data-teacher-name-preview]");
    if (!input || !preview) return;
    const sync = () => {
        let name = input.value.trim().replace(/^อาจารย์\s*/, "").replace(/^อ\.\s*/, "");
        preview.textContent = `อาจารย์${name || "ชื่อเล่น"}`;
    };
    input.addEventListener("input", sync);
    sync();
})();
