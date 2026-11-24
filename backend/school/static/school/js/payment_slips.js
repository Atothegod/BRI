(() => {
    "use strict";

    const picker = document.querySelector("[data-slip-picker]");
    if (!picker) return;

    const add = picker.querySelector("[data-slip-add]");
    const count = picker.querySelector("[data-slip-count]");
    const rows = Array.from(picker.querySelectorAll("[data-slip-row]"), (element) => ({
        element,
        input: element.querySelector('input[type="file"]'),
        name: element.querySelector("[data-slip-name]"),
        preview: element.querySelector("[data-slip-preview]"),
        remove: element.querySelector("[data-slip-remove]"),
    }));

    function updatePicker() {
        const selected = rows.filter(({input}) => input.files.length).length;
        count.textContent = `เลือกรูปแล้ว ${selected} จาก ${rows.length} ใบ`;
        add.hidden = rows.every(({element}) => !element.hidden);
    }

    rows.forEach((row, index) => {
        const {element, input, name, preview, remove} = row;
        let previewUrl;
        element.hidden = index > 0 && !input.files.length && !element.classList.contains("has-error");

        function updateRow() {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            const file = input.files[0];
            previewUrl = file ? URL.createObjectURL(file) : null;
            if (previewUrl) {
                preview.src = previewUrl;
            } else {
                preview.removeAttribute("src");
            }
            preview.hidden = !file;
            preview.previousElementSibling.hidden = Boolean(file);
            name.textContent = file ? file.name : "";
            remove.hidden = !file;
            updatePicker();
        }

        input.addEventListener("change", updateRow);
        remove.addEventListener("click", () => {
            input.value = "";
            updateRow();
            input.focus();
        });
        updateRow();
    });

    add.addEventListener("click", () => {
        const next = rows.find(({element}) => element.hidden);
        if (!next) return;
        next.element.hidden = false;
        updatePicker();
        next.input.focus();
    });

    count.hidden = false;
})();
