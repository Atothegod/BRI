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
})();
