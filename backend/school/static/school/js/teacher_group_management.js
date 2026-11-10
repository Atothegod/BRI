(() => {
    "use strict";
    const board = document.querySelector("[data-teacher-board]");
    if (!board) return;
    let lanes = Array.from(board.querySelectorAll("[data-teacher-lane]"));
    const status = board.querySelector("[data-teacher-status]");
    const createDialog = document.querySelector("#teacher-group-create-dialog");
    const moveDialog = document.querySelector("#teacher-move-dialog");
    const moveName = moveDialog?.querySelector("[data-dialog-teacher-name]");
    const targets = Array.from(moveDialog?.querySelectorAll("[data-move-target]") || []);
    const csrf = createDialog?.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
    let draggedCard = null;
    let selectedCard = null;
    let moving = false;

    const updateLane = (lane) => {
        const list = lane.querySelector("[data-lane-list]");
        const count = list?.querySelectorAll(":scope > [data-teacher-card]").length || 0;
        const counter = lane.querySelector("[data-lane-count]");
        const empty = list?.querySelector(":scope > [data-lane-empty]");
        if (counter) counter.textContent = String(count);
        if (empty) empty.hidden = count > 0;
    };
    const updateStats = () => {
        const cards = Array.from(board.querySelectorAll("[data-teacher-card]"));
        const unassigned = cards.filter((card) => card.dataset.groupId === "").length;
        document.querySelector("[data-stat-total]")?.replaceChildren(String(cards.length));
        document.querySelector("[data-stat-assigned]")?.replaceChildren(String(cards.length - unassigned));
        document.querySelector("[data-stat-unassigned]")?.replaceChildren(String(unassigned));
        lanes.forEach(updateLane);
    };
    const findLane = (groupId) => lanes.find((lane) => lane.dataset.groupId === groupId);
    const setStatus = (text, state = "") => { status.textContent = text; status.dataset.state = state; };

    const deleteGroup = async (button) => {
        if (moving) return;
        const groupNode = button.closest("[data-teacher-lane]");
        const studentCount = Number(button.dataset.studentCount || 0);
        const detail = studentCount
            ? ` นักศึกษา ${studentCount} คนจะกลับไปอยู่ในรายการรอจัดกลุ่ม`
            : "";
        if (!window.confirm(`ลบกลุ่ม “${button.dataset.groupName}” หรือไม่? อาจารย์จะกลับไปที่ Teacher Pool${detail} และประวัติเดิมจะยังอยู่`)) return;
        const pool = findLane("");
        const body = new FormData();
        body.set("action", "delete_group");
        body.set("group", button.dataset.groupId);
        if (csrf) body.set("csrfmiddlewaretoken", csrf);
        moving = true;
        groupNode.classList.add("is-deleting");
        setStatus(`กำลังลบกลุ่ม ${button.dataset.groupName}...`, "saving");
        try {
            const response = await fetch(window.location.pathname, {method:"POST", body, headers:{"X-Requested-With":"XMLHttpRequest"}, credentials:"same-origin"});
            const result = await response.json();
            if (!response.ok || !result.ok) throw new Error(result.message || "ลบกลุ่มไม่สำเร็จ");
            const poolList = pool.querySelector("[data-lane-list]");
            groupNode.querySelectorAll("[data-teacher-card]").forEach((card) => {
                card.dataset.groupId = "";
                poolList.insertBefore(card, poolList.querySelector("[data-lane-empty]"));
            });
            groupNode.remove();
            lanes = lanes.filter((lane) => lane !== groupNode);
            moveDialog.querySelector(`[data-move-target][data-group-id="${button.dataset.groupId}"]`)?.remove();
            const groupStat = document.querySelector(".teacher-group-stats > div:first-child strong");
            if (groupStat) groupStat.textContent = String(Math.max(0, Number(groupStat.textContent) - 1));
            updateStats();
            setStatus(result.message, "success");
        } catch (error) {
            groupNode.classList.remove("is-deleting");
            setStatus(error.message || "ลบกลุ่มไม่สำเร็จ", "error");
        } finally {
            moving = false;
        }
    };

    const moveTeacher = async (card, lane) => {
        if (!card || !lane || moving || card.dataset.groupId === lane.dataset.groupId) return;
        const source = card.closest("[data-teacher-lane]");
        const body = new FormData();
        body.set("teacher", card.dataset.teacherId);
        body.set("group", lane.dataset.groupId);
        if (csrf) body.set("csrfmiddlewaretoken", csrf);
        moving = true;
        card.classList.add("is-saving");
        lane.classList.add("is-receiving");
        setStatus(`กำลังย้าย ${card.dataset.teacherName}...`, "saving");
        try {
            const response = await fetch(window.location.pathname, {method: "POST", body, headers: {"X-Requested-With": "XMLHttpRequest"}, credentials: "same-origin"});
            const result = await response.json();
            if (!response.ok || !result.ok) throw new Error(result.message || "ย้ายอาจารย์ไม่สำเร็จ");
            const list = lane.querySelector("[data-lane-list]");
            list.insertBefore(card, list.querySelector("[data-lane-empty]"));
            card.dataset.groupId = lane.dataset.groupId;
            card.classList.add("is-moved");
            window.setTimeout(() => card.classList.remove("is-moved"), 800);
            if (source) updateLane(source);
            updateStats();
            setStatus(result.message, "success");
        } catch (error) {
            setStatus(error.message || "ย้ายอาจารย์ไม่สำเร็จ", "error");
        } finally {
            moving = false;
            card.classList.remove("is-saving");
            lane.classList.remove("is-receiving");
        }
    };

    board.addEventListener("dragstart", (event) => {
        const card = event.target.closest("[data-teacher-card]");
        if (!card || moving) return event.preventDefault();
        draggedCard = card;
        card.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", card.dataset.teacherId);
    });
    board.addEventListener("dragover", (event) => {
        const lane = event.target.closest("[data-teacher-lane]");
        if (!lane || !draggedCard) return;
        event.preventDefault();
        lanes.forEach((item) => item.classList.toggle("is-drag-over", item === lane));
    });
    board.addEventListener("drop", (event) => {
        const lane = event.target.closest("[data-teacher-lane]");
        if (!lane || !draggedCard) return;
        event.preventDefault();
        lanes.forEach((item) => item.classList.remove("is-drag-over"));
        moveTeacher(draggedCard, lane);
    });
    board.addEventListener("dragend", () => {
        draggedCard?.classList.remove("is-dragging");
        draggedCard = null;
        lanes.forEach((lane) => lane.classList.remove("is-drag-over"));
    });
    board.addEventListener("click", (event) => {
        const deleteButton = event.target.closest("[data-delete-group]");
        if (deleteButton) {
            deleteGroup(deleteButton);
            return;
        }
        const button = event.target.closest("[data-open-move-dialog]");
        if (!button) return;
        selectedCard = button.closest("[data-teacher-card]");
        moveName.textContent = selectedCard.dataset.teacherName;
        targets.forEach((target) => { target.disabled = target.dataset.groupId === selectedCard.dataset.groupId; });
        moveDialog.showModal();
    });
    targets.forEach((target) => target.addEventListener("click", async () => {
        const lane = findLane(target.dataset.groupId);
        moveDialog.close();
        await moveTeacher(selectedCard, lane);
        selectedCard = null;
    }));
    document.querySelectorAll("[data-open-create-group]").forEach((button) => button.addEventListener("click", () => createDialog.showModal()));
    document.querySelector("[data-close-create-group]")?.addEventListener("click", () => createDialog.close());
    document.querySelector("[data-close-move-dialog]")?.addEventListener("click", () => moveDialog.close());
    [createDialog, moveDialog].forEach((dialog) => dialog?.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); }));
    if (createDialog?.hasAttribute("data-has-errors")) createDialog.showModal();
    updateStats();
})();
