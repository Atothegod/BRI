(() => {
    "use strict";
    const textarea = document.querySelector('#line-message-text');
    const boxes = [...document.querySelectorAll('[data-recipient]')];
    const selectPage = document.querySelector('[data-select-page]');
    const sendSelected = document.querySelector('[data-send-selected]');
    const sendFiltered = document.querySelector('[data-send-filtered]');
    const selectedCount = document.querySelector('[data-selected-count]');
    const selectedButtonCount = document.querySelector('[data-selected-button-count]');
    const characterCount = document.querySelector('[data-character-count]');
    const dialog = document.querySelector('[data-send-dialog]');
    const progress = document.querySelector('[data-send-progress]');
    const progressBar = document.querySelector('[data-progress-bar]');
    const progressTitle = document.querySelector('[data-progress-title]');
    const progressDetail = document.querySelector('[data-progress-detail]');
    const csrfToken = document.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
    const urlTemplate = document.querySelector('[data-message-url-template]')?.dataset.messageUrlTemplate || '';
    const allIds = JSON.parse(document.querySelector('#all-line-recipient-ids')?.textContent || '[]').map(String);
    let pendingIds = [];
    let sending = false;

    function sync() {
        const selectable = boxes.filter(box => !box.disabled);
        const selected = selectable.filter(box => box.checked);
        selectedCount.textContent = selected.length;
        selectedButtonCount.textContent = selected.length;
        sendSelected.disabled = sending || selected.length === 0;
        if (sendFiltered) sendFiltered.disabled = sending || allIds.length === 0;
        selectPage.checked = selectable.length > 0 && selected.length === selectable.length;
        selectPage.indeterminate = selected.length > 0 && selected.length < selectable.length;
        characterCount.textContent = textarea.value.length.toLocaleString('th-TH');
    }

    function openConfirmation(ids) {
        const message = textarea.value.trim();
        if (!message) {
            textarea.focus();
            textarea.classList.add('needs-attention');
            return;
        }
        textarea.classList.remove('needs-attention');
        pendingIds = [...new Set(ids.map(String))];
        if (!pendingIds.length) return;
        dialog.querySelector('[data-dialog-count]').textContent = pendingIds.length.toLocaleString('th-TH');
        dialog.querySelector('[data-dialog-preview]').textContent = message;
        dialog.showModal();
    }

    function messageUrl(id) {
        return urlTemplate.replace('/0/', `/${id}/`);
    }

    async function sendOne(id, message) {
        const card = document.querySelector(`[data-recipient-card="${id}"]`);
        const status = card?.querySelector('[data-recipient-status]');
        if (status) status.textContent = 'กำลังส่ง';
        try {
            const response = await fetch(messageUrl(id), {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: new URLSearchParams({ message }),
            });
            const data = await response.json();
            if (status) {
                status.textContent = data.sent ? 'ส่งแล้ว' : (data.error || 'ส่งไม่สำเร็จ');
                status.className = data.sent ? 'sent' : 'failed';
            }
            return !!data.sent;
        } catch (_) {
            if (status) { status.textContent = 'เชื่อมต่อไม่สำเร็จ'; status.className = 'failed'; }
            return false;
        }
    }

    async function runBatch(ids) {
        if (sending) return;
        sending = true;
        sync();
        const message = textarea.value.trim();
        progress.hidden = false;
        progressBar.max = ids.length;
        progressBar.value = 0;
        let cursor = 0;
        let sent = 0;
        async function worker() {
            while (cursor < ids.length) {
                const index = cursor++;
                if (await sendOne(ids[index], message)) sent++;
                progressBar.value += 1;
                progressDetail.textContent = `${progressBar.value}/${ids.length} คน`;
            }
        }
        await Promise.all(Array.from({ length: Math.min(4, ids.length) }, worker));
        progressTitle.textContent = `ส่งเสร็จ ${sent}/${ids.length} คน`;
        progressDetail.textContent = sent === ids.length ? 'LINE รับข้อความครบทุกคน' : `ส่งไม่สำเร็จ ${ids.length - sent} คน`;
        progress.classList.toggle('has-error', sent !== ids.length);
        sending = false;
        sync();
    }

    textarea.addEventListener('input', sync);
    boxes.forEach(box => box.addEventListener('change', sync));
    selectPage.addEventListener('change', () => {
        boxes.filter(box => !box.disabled).forEach(box => { box.checked = selectPage.checked; });
        sync();
    });
    sendSelected.addEventListener('click', () => openConfirmation(boxes.filter(box => box.checked).map(box => box.value)));
    sendFiltered?.addEventListener('click', () => openConfirmation(allIds));
    document.querySelectorAll('[data-send-one]').forEach(button => button.addEventListener('click', () => openConfirmation([button.dataset.sendOne])));
    dialog.addEventListener('close', () => {
        if (dialog.returnValue === 'confirm') runBatch(pendingIds);
        pendingIds = [];
    });
    sync();
})();
