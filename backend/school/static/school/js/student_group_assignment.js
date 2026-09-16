(() => {
    const form = document.querySelector("#assignment-form");
    if (!form) return;

    const checkboxes = Array.from(form.querySelectorAll('input[name="students"]'));
    const rows = Array.from(form.querySelectorAll("[data-student-row]"));
    const selectAll = form.querySelector("#select-all");
    const selectedCount = form.querySelector("#selected-count");
    const selectedPreview = form.querySelector("#selected-preview");
    const groupOptions = Array.from(form.querySelectorAll('input[name="group"]'));
    const submit = form.querySelector("#confirm-assignment");
    const warning = form.querySelector("#reassignment-warning");
    const hint = form.querySelector("#assignment-hint");
    const reviewDialog = form.querySelector("#assignment-review-dialog");
    const reviewStudentCount = form.querySelector("#review-student-count");
    const reviewGroupName = form.querySelector("#review-group-name");
    const reviewTeacherName = form.querySelector("#review-teacher-name");
    const reviewWarning = form.querySelector("#review-warning");
    const cancelAssignment = form.querySelector("#cancel-assignment");
    const finalConfirm = form.querySelector("#final-confirm-assignment");

    const selectedStudents = () => checkboxes.filter((checkbox) => checkbox.checked);
    const selectedGroup = () => groupOptions.find((option) => option.checked);

    const refresh = () => {
        const selected = selectedStudents();
        const group = selectedGroup();
        const count = selected.length;
        const reassignmentCount = selected.filter((checkbox) => (
            checkbox.closest("[data-student-row]")?.dataset.hasGroup === "true"
        )).length;
        const names = selected.map((checkbox) => (
            checkbox.closest("[data-student-row]")?.dataset.studentName || ""
        )).filter(Boolean);

        selectedCount.textContent = String(count);
        submit.disabled = count === 0 || !group;
        rows.forEach((row) => {
            const checkbox = row.querySelector('input[name="students"]');
            row.classList.toggle("is-selected", Boolean(checkbox?.checked));
            row.setAttribute("aria-selected", checkbox?.checked ? "true" : "false");
        });

        if (count === 0) {
            selectedPreview.textContent = "ยังไม่ได้เลือกนักศึกษา";
        } else {
            const visibleNames = names.slice(0, 3).join(", ");
            const remaining = count - 3;
            selectedPreview.textContent = remaining > 0
                ? `${visibleNames} และอีก ${remaining} คน`
                : visibleNames;
        }

        warning.hidden = reassignmentCount === 0;
        warning.textContent = reassignmentCount
            ? `${reassignmentCount} คนมีกลุ่มอยู่แล้วและจะถูกย้ายมายังกลุ่มใหม่`
            : "";

        if (count === 0) {
            hint.textContent = "เลือกนักศึกษาเพื่อเริ่มจัดกลุ่ม";
        } else if (!group) {
            hint.textContent = "เลือกกลุ่มปลายทาง";
        } else {
            hint.textContent = `พร้อมจัด ${count} คนเข้า ${group.dataset.groupLabel}`;
        }

        if (selectAll) {
            selectAll.checked = checkboxes.length > 0 && count === checkboxes.length;
            selectAll.indeterminate = count > 0 && count < checkboxes.length;
        }
    };

    const toggleRow = (row) => {
        const checkbox = row.querySelector('input[name="students"]');
        if (!checkbox) return;
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    };

    checkboxes.forEach((checkbox) => checkbox.addEventListener("change", refresh));
    groupOptions.forEach((option) => option.addEventListener("change", refresh));
    rows.forEach((row) => {
        row.addEventListener("click", (event) => {
            if (event.target.closest("input, button, a, label, select")) return;
            toggleRow(row);
        });
        row.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            if (event.target.closest("input, button, a, label, select")) return;
            event.preventDefault();
            toggleRow(row);
        });
    });
    selectAll?.addEventListener("change", () => {
        checkboxes.forEach((checkbox) => { checkbox.checked = selectAll.checked; });
        refresh();
    });

    form.addEventListener("submit", (event) => {
        const selected = selectedStudents();
        const group = selectedGroup();
        if (form.dataset.confirmed === "true") return;

        event.preventDefault();
        if (!selected.length || !group) {
            refresh();
            return;
        }

        const reassignmentCount = selected.filter((checkbox) => (
            checkbox.closest("[data-student-row]")?.dataset.hasGroup === "true"
        )).length;
        reviewStudentCount.textContent = `${selected.length} คน`;
        reviewGroupName.textContent = group.dataset.groupLabel || "-";
        reviewTeacherName.textContent = group.dataset.groupTeacher || "-";
        reviewWarning.hidden = reassignmentCount === 0;
        reviewWarning.textContent = reassignmentCount
            ? `${reassignmentCount} คนจะถูกย้ายออกจากกลุ่มเดิม`
            : "";

        if (typeof reviewDialog?.showModal === "function") {
            reviewDialog.showModal();
            return;
        }

        const message = `ยืนยันจัดนักศึกษา ${selected.length} คนเข้า ${group.dataset.groupLabel}?`;
        if (window.confirm(message)) {
            form.dataset.confirmed = "true";
            form.requestSubmit(submit);
        }
    });

    cancelAssignment?.addEventListener("click", () => reviewDialog?.close());
    finalConfirm?.addEventListener("click", () => {
        form.dataset.confirmed = "true";
        reviewDialog?.close();
        form.requestSubmit(submit);
    });
    reviewDialog?.addEventListener("click", (event) => {
        if (event.target === reviewDialog) reviewDialog.close();
    });

    refresh();
})();
