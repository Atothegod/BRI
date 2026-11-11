(() => {
    const search = document.querySelector("[data-learning-search]");
    const rows = [...document.querySelectorAll("[data-learning-row]")];
    const buttons = [...document.querySelectorAll("[data-learning-filter]")];
    const empty = document.querySelector("[data-learning-empty]");
    let filter = "all";
    const sync = () => {
        const query = (search?.value || "").trim().toLocaleLowerCase("th");
        let visible = 0;
        rows.forEach((row) => {
            const matchesText = !query || (row.dataset.search || "").toLocaleLowerCase("th").includes(query);
            const matchesFilter = filter === "all" || row.dataset.follow === "true";
            row.hidden = !(matchesText && matchesFilter);
            if (!row.hidden) visible += 1;
        });
        if (empty) empty.hidden = visible > 0 || rows.length === 0;
    };
    search?.addEventListener("input", sync);
    buttons.forEach((button) => button.addEventListener("click", () => {
        filter = button.dataset.learningFilter || "all";
        buttons.forEach((item) => item.classList.toggle("is-active", item === button));
        sync();
    }));
})();
