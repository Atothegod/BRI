document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    document.querySelectorAll("[data-admin-slip-picker]").forEach((input) => {
        if (typeof DataTransfer !== "function") return;

        const chooser = input.cloneNode();
        chooser.removeAttribute("name");
        chooser.setAttribute("aria-label", "เลือกรูปสลิปเพิ่ม");
        input.removeAttribute("id");
        input.hidden = true;
        input.tabIndex = -1;
        input.after(chooser);

        const status = document.createElement("p");
        status.setAttribute("role", "status");
        const previews = document.createElement("ul");
        previews.style.cssText = "display:flex;flex-wrap:wrap;gap:12px;margin-top:8px";
        chooser.after(status, previews);

        let selected = Array.from(input.files);
        let previewUrls = [];

        function render() {
            const transfer = new DataTransfer();
            selected.forEach((file) => transfer.items.add(file));
            input.files = transfer.files;

            previewUrls.forEach((url) => URL.revokeObjectURL(url));
            previewUrls = [];
            previews.replaceChildren();
            status.textContent = selected.length
                ? `เลือกแล้ว ${selected.length} ใบ · กดบันทึกเมื่อพร้อม`
                : "เลือกหลายรูปพร้อมกัน หรือกดเลือกไฟล์เพิ่มได้";

            selected.forEach((file, index) => {
                const row = document.createElement("li");
                const url = URL.createObjectURL(file);
                previewUrls.push(url);

                const link = document.createElement("a");
                link.href = url;
                link.target = "_blank";
                link.rel = "noopener";
                const image = document.createElement("img");
                image.src = url;
                image.alt = `พรีวิวสลิปใบที่ ${index + 1}`;
                image.style.cssText = "width:120px;height:150px;object-fit:contain";
                link.append(image);

                const filename = document.createElement("p");
                filename.textContent = file.name;
                filename.style.cssText = "max-width:120px;overflow-wrap:anywhere";
                const remove = document.createElement("button");
                remove.type = "button";
                remove.textContent = "เอารูปนี้ออก";
                remove.setAttribute("aria-label", `เอาสลิปใบที่ ${index + 1} ออก`);
                remove.addEventListener("click", () => {
                    selected.splice(index, 1);
                    render();
                    chooser.focus();
                });
                row.append(link, filename, remove);
                previews.append(row);
            });
        }

        chooser.addEventListener("change", () => {
            selected.push(...chooser.files);
            chooser.value = "";
            render();
        });
        render();
    });
});
