(() => {
    "use strict";
    const roster = document.querySelector("[data-attendance-roster]");
    if (!roster) return;
    const csrf = roster.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
    const statusBox = roster.querySelector("[data-roster-status]");
    let saving = false;

    const updateCounts = () => {
        document.querySelectorAll("[data-count-status]").forEach((card) => {
            const count = roster.querySelectorAll(`[data-roster-row][data-status="${card.dataset.countStatus}"]`).length;
            card.querySelector("strong").textContent = String(count);
        });
    };
    const applyRows = (rows) => {
        rows.forEach((item) => {
            const row = roster.querySelector(`[data-roster-row][data-student-id="${item.student_id}"]`);
            if (!row) return;
            row.dataset.status = item.status;
            row.querySelector("[data-record-state]").textContent = item.status_label;
            row.querySelector("[data-checkin-time]").textContent = item.checked_in_time ? `${item.checked_in_time} น.` : "";
            const picker = row.querySelector(".attendance-status-picker");
            if (item.locked) picker.setAttribute("data-locked", ""); else picker.removeAttribute("data-locked");
            picker.querySelectorAll("[data-set-status]").forEach((button) => button.classList.toggle("is-active", button.dataset.setStatus === item.status));
        });
        updateCounts();
    };
    roster.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-set-status]");
        const row = button?.closest("[data-roster-row]");
        if (!button || !row || saving || button.classList.contains("is-active")) return;
        if (button.closest("[data-locked]")) {
            statusBox.textContent = "นักศึกษาคนนี้เช็กอินแล้ว หากข้อมูลผิดให้ School Admin เป็นผู้แก้ไข";
            statusBox.dataset.state = "error";
            return;
        }
        const body = new FormData();
        body.set("student", row.dataset.studentId);
        body.set("status", button.dataset.setStatus);
        if (csrf) body.set("csrfmiddlewaretoken", csrf);
        saving = true;
        row.classList.add("is-saving");
        statusBox.textContent = "กำลังบันทึกสถานะ...";
        statusBox.dataset.state = "saving";
        try {
            const response = await fetch(window.location.pathname, {method:"POST", body, headers:{"X-Requested-With":"XMLHttpRequest"}, credentials:"same-origin"});
            const result = await response.json();
            if (!response.ok || !result.ok) throw new Error(result.message || "บันทึกไม่สำเร็จ");
            row.dataset.status = result.status;
            row.querySelectorAll("[data-set-status]").forEach((item) => item.classList.toggle("is-active", item.dataset.setStatus === result.status));
            updateCounts();
            statusBox.textContent = result.message;
            statusBox.dataset.state = "success";
        } catch (error) {
            statusBox.textContent = error.message || "บันทึกไม่สำเร็จ";
            statusBox.dataset.state = "error";
        } finally {
            saving = false;
            row.classList.remove("is-saving");
        }
    });
    window.setInterval(async () => {
        if (saving || document.hidden) return;
        try {
            const response = await fetch(`${window.location.pathname}?poll=1`, {headers:{"X-Requested-With":"XMLHttpRequest"}, credentials:"same-origin"});
            const result = await response.json();
            if (response.ok && result.ok) applyRows(result.rows);
        } catch { /* keep the current roster when a background refresh fails */ }
    }, 15000);
})();
