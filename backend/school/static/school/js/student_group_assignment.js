(() => {
    const form = document.querySelector("#assignment-board-form");
    const board = form?.querySelector("[data-assignment-board]");
    if (!form || !board) return;

    const lanes = Array.from(board.querySelectorAll("[data-assignment-lane]"));
    const status = board.querySelector("[data-board-status]");
    const statusText = board.querySelector("[data-board-status-text]");
    const totalStat = document.querySelector("[data-stat-total]");
    const unassignedStat = document.querySelector("[data-stat-unassigned]");
    const assignedStat = document.querySelector("[data-stat-assigned]");
    const dialog = form.querySelector("#student-move-dialog");
    const dialogStudentName = dialog?.querySelector("[data-dialog-student-name]");
    const moveTargets = Array.from(dialog?.querySelectorAll("[data-move-target]") || []);
    const closeDialog = dialog?.querySelector("[data-close-move-dialog]");

    let draggedCard = null;
    let dialogCard = null;
    let isMoving = false;

    const cards = () => Array.from(board.querySelectorAll("[data-student-card]"));

    const setStatus = (message, state = "idle") => {
        statusText.textContent = message;
        status.dataset.state = state;
    };

    const updateLane = (lane) => {
        const list = lane.querySelector("[data-lane-list]");
        if (!list) return;
        const count = list.querySelectorAll(":scope > [data-student-card]").length;
        const counter = lane.querySelector("[data-lane-count]");
        const empty = list.querySelector(":scope > [data-lane-empty]");
        if (counter) counter.textContent = String(count);
        if (empty) empty.hidden = count > 0;
    };

    const updateStats = () => {
        const allCards = cards();
        const unassigned = allCards.filter((card) => card.dataset.groupId === "").length;
        if (totalStat) totalStat.textContent = String(allCards.length);
        if (unassignedStat) unassignedStat.textContent = String(unassigned);
        if (assignedStat) assignedStat.textContent = String(allCards.length - unassigned);
        lanes.forEach(updateLane);
    };

    const findLane = (groupId) => lanes.find((lane) => lane.dataset.groupId === groupId);

    const moveStudent = async (card, destinationLane) => {
        if (!card || !destinationLane || isMoving) return;
        const destinationGroupId = destinationLane.dataset.groupId;
        if (card.dataset.groupId === destinationGroupId) {
            setStatus(`${card.dataset.studentName} อยู่ใน ${destinationLane.dataset.groupName} แล้ว`);
            return;
        }

        const sourceLane = card.closest(".assignment-lane");
        const destinationList = destinationLane.querySelector("[data-lane-list]");
        const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
        const payload = new FormData();
        payload.set("student", card.dataset.studentId);
        payload.set("group", destinationGroupId);
        if (csrfToken) payload.set("csrfmiddlewaretoken", csrfToken);

        isMoving = true;
        card.classList.add("is-saving");
        destinationLane.classList.add("is-receiving");
        setStatus(`กำลังย้าย ${card.dataset.studentName}...`, "saving");

        try {
            const response = await fetch(window.location.pathname, {
                method: "POST",
                body: payload,
                headers: { "X-Requested-With": "XMLHttpRequest" },
                credentials: "same-origin",
            });
            let result;
            try {
                result = await response.json();
            } catch {
                throw new Error("ระบบตอบกลับไม่ถูกต้อง กรุณาลองใหม่");
            }
            if (!response.ok || !result.ok) {
                throw new Error(result.message || "ไม่สามารถย้ายกลุ่มได้");
            }

            destinationList.insertBefore(card, destinationList.querySelector("[data-lane-empty]"));
            card.dataset.groupId = destinationGroupId;
            card.classList.add("is-just-moved");
            window.setTimeout(() => card.classList.remove("is-just-moved"), 900);
            if (sourceLane) updateLane(sourceLane);
            updateLane(destinationLane);
            updateStats();
            setStatus(result.message, "success");
        } catch (error) {
            setStatus(error.message || "ไม่สามารถย้ายกลุ่มได้ กรุณาลองใหม่", "error");
        } finally {
            isMoving = false;
            card.classList.remove("is-saving");
            destinationLane.classList.remove("is-receiving");
        }
    };

    board.addEventListener("dragstart", (event) => {
        const card = event.target.closest("[data-student-card]");
        if (!card || isMoving) {
            event.preventDefault();
            return;
        }
        draggedCard = card;
        card.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", card.dataset.studentId);
    });

    board.addEventListener("dragover", (event) => {
        const lane = event.target.closest("[data-assignment-lane]");
        if (!lane || !draggedCard) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        lanes.forEach((item) => item.classList.toggle("is-drag-over", item === lane));
    });

    board.addEventListener("drop", (event) => {
        const lane = event.target.closest("[data-assignment-lane]");
        if (!lane || !draggedCard) return;
        event.preventDefault();
        lanes.forEach((item) => item.classList.remove("is-drag-over"));
        moveStudent(draggedCard, lane);
    });

    board.addEventListener("dragend", () => {
        draggedCard?.classList.remove("is-dragging");
        draggedCard = null;
        lanes.forEach((lane) => lane.classList.remove("is-drag-over"));
    });

    board.addEventListener("click", (event) => {
        const button = event.target.closest("[data-open-move-dialog]");
        if (!button || isMoving) return;
        dialogCard = button.closest("[data-student-card]");
        if (!dialogCard || !dialog) return;

        dialogStudentName.textContent = dialogCard.dataset.studentName;
        moveTargets.forEach((target) => {
            const isCurrent = target.dataset.groupId === dialogCard.dataset.groupId;
            target.disabled = isCurrent;
            target.classList.toggle("is-current", isCurrent);
        });
        if (typeof dialog.showModal === "function") dialog.showModal();
    });

    moveTargets.forEach((target) => {
        target.addEventListener("click", async () => {
            const destinationLane = findLane(target.dataset.groupId);
            if (!dialogCard || !destinationLane) return;
            dialog.close();
            await moveStudent(dialogCard, destinationLane);
            dialogCard = null;
        });
    });

    closeDialog?.addEventListener("click", () => dialog?.close());
    dialog?.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
    });

    updateStats();
})();
