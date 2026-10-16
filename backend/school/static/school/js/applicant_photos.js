document.querySelectorAll("[data-photo-form]").forEach((form) => {
    const input = form.querySelector("[data-photo-input]");
    input.addEventListener("change", () => {
        const file = input.files?.[0];
        if (!file) return;
        const frame = form.closest(".applicant-card").querySelector("[data-photo-frame]");
        let preview = frame.querySelector("[data-photo-preview]");
        if (!preview) {
            preview = document.createElement("img");
            preview.dataset.photoPreview = "";
            frame.querySelector("[data-photo-placeholder]")?.remove();
            frame.prepend(preview);
        }
        preview.src = URL.createObjectURL(file);
        preview.alt = `ตัวอย่างรูป ${file.name}`;
        frame.querySelector("[data-uploading]").hidden = false;
        form.requestSubmit();
    });
});

document.querySelectorAll("[data-delete-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        const name = form.dataset.personName || "ผู้สมัครคนนี้";
        if (!window.confirm(`ยืนยันลบรูปของ ${name}? การดำเนินการนี้ไม่สามารถย้อนกลับได้`)) event.preventDefault();
    });
});
