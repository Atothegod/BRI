(() => {
    "use strict";
    const search = document.querySelector("[data-teacher-student-search]");
    const rows = [...document.querySelectorAll("[data-teacher-student-row]")];
    const empty = document.querySelector("[data-teacher-search-empty]");
    const filterButtons = [...document.querySelectorAll("[data-student-filter]")];
    let activeFilter = "all";
    const syncSearch = () => {
        const query = (search?.value || "").trim().toLocaleLowerCase("th");
        let visible = 0;
        rows.forEach((row) => {
            const matchesQuery = !query || (row.dataset.searchText || "").toLocaleLowerCase("th").includes(query);
            const matchesFilter = activeFilter === "all" || row.dataset.needsAttention === "true";
            const matches = matchesQuery && matchesFilter;
            row.hidden = !matches;
            if (matches) visible += 1;
        });
        if (empty) empty.hidden = visible > 0 || rows.length === 0;
    };
    search?.addEventListener("input", syncSearch);

    const updateAttentionUi = (row, needsCare) => {
        if (!row) return;
        const wasAttention = row.dataset.needsAttention === "true";
        const isAttention = needsCare || row.dataset.automaticAttention === "true";
        row.dataset.needsAttention = isAttention ? "true" : "false";
        row.classList.toggle("needs-attention", isAttention);
        const status = row.querySelector("[data-student-status] > span");
        if (status) {
            status.textContent = isAttention ? "ควรติดตาม" : "ปกติ";
            status.className = `status-label status-label--${isAttention ? "attention" : "ok"}`;
        }
        if (wasAttention !== isAttention) {
            document.querySelectorAll("[data-attention-count]").forEach((counter) => {
                counter.textContent = String(Math.max(0, Number(counter.textContent) + (isAttention ? 1 : -1)));
            });
        }
        const list = document.querySelector("[data-attention-list]");
        const existing = list?.querySelector(`[data-attention-student="${row.dataset.studentId}"]`);
        if (isAttention && !existing && list) {
            list.querySelector(".teacher-positive-empty")?.remove();
            const article = document.createElement("article");
            article.dataset.attentionStudent = row.dataset.studentId;
            article.innerHTML = `<span class="attention-avatar">${(row.dataset.studentName || "?").slice(0, 1)}</span><div><strong></strong><small></small></div>`;
            article.querySelector("strong").textContent = row.dataset.studentName || "นักศึกษา";
            article.querySelector("small").textContent = `${row.dataset.studentGroup || ""} · 💔 ต้องดูแล`;
            list.prepend(article);
        } else if (!isAttention) {
            existing?.remove();
        }
        syncSearch();
    };
    filterButtons.forEach((button) => button.addEventListener("click", () => {
        activeFilter = button.dataset.studentFilter || "all";
        filterButtons.forEach((item) => {
            const selected = item === button;
            item.classList.toggle("is-active", selected);
            item.setAttribute("aria-pressed", selected ? "true" : "false");
        });
        syncSearch();
    }));

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
                updateAttentionUi(summary?.closest("[data-teacher-student-row]"), result.assessment.needs_care);
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
