(() => {
    const unsavedForms = new Set();

    function warnAboutUnsavedChanges(event) {
        event.preventDefault();
        event.returnValue = true;
    }

    document.querySelectorAll("[data-result-form]").forEach((form) => {
        const comment = form.elements.interview_comment;
        const commentStatus = form.querySelector("[data-comment-status]");
        const retryButton = form.querySelector(".comment-save");
        const gradeButtons = Array.from(form.querySelectorAll("[data-grade-value]"));
        const gradeStatus = form.querySelector("[data-grade-status]");
        let savedComment = comment.value;
        let commentTimer;
        let commentRequest;
        let gradeSaving = false;

        function updateUnloadWarning() {
            if (comment.value !== savedComment || commentRequest || gradeSaving) {
                unsavedForms.add(form);
                window.addEventListener("beforeunload", warnAboutUnsavedChanges);
            } else {
                unsavedForms.delete(form);
                if (!unsavedForms.size) {
                    window.removeEventListener("beforeunload", warnAboutUnsavedChanges);
                }
            }
        }

        async function save(action, fields) {
            const body = new URLSearchParams({
                csrfmiddlewaretoken: form.elements.csrfmiddlewaretoken.value,
                person: form.elements.person.value,
                action,
                ...fields,
            });
            const response = await fetch(form.getAttribute("action") || window.location.href, {
                method: "POST",
                headers: { Accept: "application/json" },
                body,
            });
            if (!response.ok || !(await response.json()).saved) {
                throw new Error("Save failed");
            }
        }

        async function saveComment() {
            clearTimeout(commentTimer);
            if (commentRequest) return commentRequest;
            if (comment.value === savedComment) return true;

            const submittedComment = comment.value;
            commentStatus.textContent = "กำลังบันทึกคอมเมนต์…";
            retryButton.hidden = true;

            commentRequest = save("comment", { interview_comment: submittedComment }).then(
                () => {
                    savedComment = submittedComment;
                    commentRequest = null;
                    updateUnloadWarning();
                    if (comment.value !== savedComment) return saveComment();
                    commentStatus.textContent = "บันทึกคอมเมนต์แล้ว";
                    return true;
                },
                () => {
                    commentRequest = null;
                    updateUnloadWarning();
                    commentStatus.textContent = "บันทึกคอมเมนต์ไม่สำเร็จ";
                    retryButton.hidden = false;
                    return false;
                },
            );
            updateUnloadWarning();
            return commentRequest;
        }

        saveComments.set(form, saveComment);
        retryButton.hidden = true;
        commentStatus.textContent = "บันทึกอัตโนมัติ";
        comment.addEventListener("input", () => {
            updateUnloadWarning();
            clearTimeout(commentTimer);
            retryButton.hidden = true;
            commentStatus.textContent = comment.value === savedComment
                ? "บันทึกอัตโนมัติ"
                : "รอบันทึกคอมเมนต์…";
            commentTimer = setTimeout(saveComment, 650);
        });
        comment.addEventListener("blur", saveComment);

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const grade = event.submitter?.dataset.gradeValue;
            if (!grade) {
                await saveComment();
                return;
            }
            if (gradeSaving) return;

            gradeSaving = true;
            updateUnloadWarning();
            gradeStatus.textContent = "กำลังบันทึกเกรด…";
            try {
                await save("grade", { interview_grade: grade });
                gradeButtons.forEach((button) => {
                    const selected = button.dataset.gradeValue === grade;
                    button.classList.toggle("active", selected);
                    button.setAttribute("aria-pressed", String(selected));
                });
                gradeStatus.textContent = `เกรดปัจจุบัน ${grade}`;
            } catch {
                gradeStatus.textContent = "บันทึกเกรดไม่สำเร็จ กรุณาเลือกเกรดอีกครั้ง";
            } finally {
                gradeSaving = false;
                updateUnloadWarning();
            }
        });
    });
})();
