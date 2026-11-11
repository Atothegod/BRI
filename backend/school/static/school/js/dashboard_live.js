(() => {
    "use strict";
    const root = document.querySelector("[data-live-dashboard]");
    if (!root) return;

    const replaceContents = (currentDoc, nextDoc, selector) => {
        const current = currentDoc.querySelector(selector);
        const next = nextDoc.querySelector(selector);
        if (current && next && current.innerHTML !== next.innerHTML) current.innerHTML = next.innerHTML;
    };

    const syncTeacher = (nextDoc) => {
        replaceContents(document, nextDoc, ".teacher-summary");
        replaceContents(document, nextDoc, ".teacher-attention");
        replaceContents(document, nextDoc, ".teacher-groups-overview");
        document.querySelectorAll("[data-teacher-student-row]").forEach((row) => {
            const next = nextDoc.querySelector(`[data-teacher-student-row][data-student-id="${row.dataset.studentId}"]`);
            if (!next) return;
            row.dataset.needsAttention = next.dataset.needsAttention;
            row.dataset.automaticAttention = next.dataset.automaticAttention;
            row.classList.toggle("needs-attention", next.classList.contains("needs-attention"));
            const summary = row.querySelector("[data-assessment-summary]");
            const nextSummary = next.querySelector("[data-assessment-summary]");
            if (summary && nextSummary) summary.innerHTML = nextSummary.innerHTML;
            const status = row.querySelector("[data-student-status]");
            const nextStatus = next.querySelector("[data-student-status]");
            if (status && nextStatus) status.innerHTML = nextStatus.innerHTML;
        });
    };

    const syncStudent = (nextDoc) => {
        [
            ".student-profile-grid",
            ".student-attendance-summary",
            ".student-homework-preview",
            ".student-class-panel",
            ".student-attendance-panel",
        ].forEach((selector) => replaceContents(document, nextDoc, selector));
    };

    const poll = async () => {
        if (document.hidden || document.querySelector("dialog[open]")) return;
        try {
            const response = await fetch(window.location.href, {
                credentials: "same-origin",
                cache: "no-store",
                headers: {"X-Dashboard-Live": "1"},
            });
            if (!response.ok) return;
            const nextDoc = new DOMParser().parseFromString(await response.text(), "text/html");
            if (root.dataset.liveDashboard === "teacher") syncTeacher(nextDoc);
            if (root.dataset.liveDashboard === "student") syncStudent(nextDoc);
        } catch (_) {
            // Keep the current dashboard usable while the connection is offline.
        }
    };

    window.setInterval(poll, 15000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
})();
