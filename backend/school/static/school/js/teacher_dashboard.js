(() => {
    "use strict";
    const search = document.querySelector("[data-teacher-student-search]");
    const rows = [...document.querySelectorAll("[data-teacher-student-row]")];
    const empty = document.querySelector("[data-teacher-search-empty]");
    const syncSearch = () => {
        const query = (search?.value || "").trim().toLocaleLowerCase("th");
        let visible = 0;
        rows.forEach((row) => {
            const matches = !query || (row.dataset.searchText || "").toLocaleLowerCase("th").includes(query);
            row.hidden = !matches;
            if (matches) visible += 1;
        });
        if (empty) empty.hidden = visible > 0 || rows.length === 0;
    };
    search?.addEventListener("input", syncSearch);

    document.querySelectorAll("[data-student-detail-open]").forEach((button) => {
        button.addEventListener("click", () => document.getElementById(button.dataset.studentDetailOpen)?.showModal());
    });
    document.querySelectorAll("[data-student-detail-dialog]").forEach((dialog) => {
        dialog.querySelectorAll("[data-student-detail-close]").forEach((button) => button.addEventListener("click", () => dialog.close()));
        dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    });

    document.querySelectorAll("[data-teacher-assessment-form]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (form.classList.contains("is-saving")) return;
            const status = form.querySelector("[data-assessment-status]");
            form.classList.add("is-saving");
            if (status) {
                status.textContent = "กำลังบันทึก...";
                status.dataset.state = "saving";
            }
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                    credentials: "same-origin",
                    headers: {"X-Requested-With": "XMLHttpRequest"},
                });
                const result = await response.json();
                if (!response.ok || !result.ok) throw new Error(result.message || "บันทึกไม่สำเร็จ");
                const summary = document.querySelector(`[data-assessment-summary="${form.dataset.studentId}"]`);
                if (summary) {
                    summary.querySelector("strong").textContent = result.assessment.grade || "-";
                    const heart = summary.querySelector("span");
                    heart.hidden = !result.assessment.needs_care;
                }
                if (result.assessment.needs_care) {
                    summary?.closest("[data-teacher-student-row]")?.classList.add("needs-attention");
                }
                if (status) {
                    status.textContent = `${result.message} · ${result.assessment.updated_at}`;
                    status.dataset.state = "success";
                }
            } catch (error) {
                if (status) {
                    status.textContent = error.message || "บันทึกไม่สำเร็จ";
                    status.dataset.state = "error";
                }
            } finally {
                form.classList.remove("is-saving");
            }
        });
    });
})();
