(() => {
    const form = document.querySelector("#assignment-form");
    if (!form) return;

    const checkboxes = Array.from(form.querySelectorAll('input[name="students"]'));
    const selectAll = form.querySelector("#select-all");
    const selectedCount = form.querySelector("#selected-count");
    const group = form.querySelector("#id_group");
    const submit = form.querySelector("#confirm-assignment");
    const warning = form.querySelector("#reassignment-warning");

    const refresh = () => {
        const selected = checkboxes.filter((checkbox) => checkbox.checked);
        const count = selected.length;
        const reassignmentCount = selected.filter((checkbox) => (
            checkbox.closest("[data-student-row]")?.dataset.hasGroup === "true"
        )).length;
        selectedCount.textContent = String(count);
        submit.disabled = count === 0 || !group.value;
        checkboxes.forEach((checkbox) => {
            checkbox.closest("[data-student-row]")?.classList.toggle("is-selected", checkbox.checked);
        });
        warning.hidden = reassignmentCount === 0;
        warning.textContent = reassignmentCount
            ? `${reassignmentCount} คนมีกลุ่มอยู่แล้วและจะถูกย้ายกลุ่ม`
            : "";
        if (selectAll) {
            selectAll.checked = checkboxes.length > 0 && count === checkboxes.length;
            selectAll.indeterminate = count > 0 && count < checkboxes.length;
        }
    };

    checkboxes.forEach((checkbox) => checkbox.addEventListener("change", refresh));
    group.addEventListener("change", refresh);
    selectAll?.addEventListener("change", () => {
        checkboxes.forEach((checkbox) => { checkbox.checked = selectAll.checked; });
        refresh();
    });
    form.addEventListener("submit", (event) => {
        const count = checkboxes.filter((checkbox) => checkbox.checked).length;
        const label = group.options[group.selectedIndex]?.text || "กลุ่มที่เลือก";
        if (!count || !group.value || !window.confirm(`ยืนยันจัดนักศึกษา ${count} คนเข้า ${label}?`)) {
            event.preventDefault();
        }
    });
    refresh();
})();
