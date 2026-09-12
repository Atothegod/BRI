(() => {
    const form = document.querySelector('#schedule-form');
    const boxes = [...form.querySelectorAll('[name="people"]')];
    const selectAll = document.querySelector('#select-all');
    const submit = document.querySelector('#confirm-schedule');
    let busy = false;
    function sync() {
        const count = boxes.filter(box => box.checked).length;
        document.querySelector('#selected-count').textContent = count;
        submit.disabled = busy || count === 0;
        selectAll.checked = count > 0 && count === boxes.length;
        selectAll.indeterminate = count > 0 && count < boxes.length;
    }
    boxes.forEach(box => box.addEventListener('change', sync));
    selectAll.addEventListener('change', () => { boxes.forEach(box => { box.checked = selectAll.checked; }); sync(); });
    form.addEventListener('submit', event => {
        const count = boxes.filter(box => box.checked).length;
        if (busy || !window.confirm(`ยืนยันนัดสัมภาษณ์ ${count} คน วันที่ ${form.elements.date.value} เวลา ${form.elements.time.value} (ประเทศไทย)? นัดเดิมของคนที่เลือกจะถูกแทนที่`)) event.preventDefault();
        else { busy = true; sync(); }
    });
    async function send(item) {
        const status = document.querySelector(`[data-status="${item.id}"]`);
        const button = document.querySelector(`[data-notify="${item.id}"]`);
        if (button) button.disabled = true;
        if (status) status.textContent = 'กำลังส่ง...';
        try {
            const response = await fetch(item.url || `${window.location.pathname}${item.id}/notify/`, {
                method: 'POST', headers: { 'X-CSRFToken': form.elements.csrfmiddlewaretoken.value },
                body: new URLSearchParams({ at: item.at }),
            });
            const data = await response.json();
            if (status) { status.textContent = data.label || data.error; status.className = data.sent ? 'state-sent' : 'state-failed'; }
            if (button && data.sent) button.hidden = true;
            return !!data.sent;
        } catch (_) {
            if (status) { status.textContent = 'เชื่อมต่อไม่สำเร็จ กรุณาลองใหม่'; status.className = 'state-failed'; }
            return false;
        } finally { if (button) button.disabled = false; }
    }
    document.querySelectorAll('[data-notify]').forEach(button => button.addEventListener('click', () => send({ id: button.dataset.notify, at: button.dataset.at, url: button.dataset.url })));
    async function runQueue() {
        const queue = JSON.parse(document.querySelector('#interview-queue').textContent);
        if (!queue.length) return;
        busy = true; sync();
        const summary = document.querySelector('#send-summary'); summary.hidden = false;
        let sent = 0;
        for (let index = 0; index < queue.length; index++) {
            summary.textContent = `กำลังแจ้ง LINE ${index + 1}/${queue.length}`;
            if (await send(queue[index])) sent++;
        }
        summary.textContent = `บันทึกนัดแล้ว ${queue.length} คน · LINE รับข้อความแล้ว ${sent} คน · ส่งไม่สำเร็จ ${queue.length - sent} คน`;
        busy = false; sync();
    }
    async function refreshConfirmations() {
        const cells = [...document.querySelectorAll('[data-confirmation]')];
        if (!cells.length || document.hidden) return;
        try {
            const body = new URLSearchParams();
            cells.forEach(cell => body.append('people', cell.dataset.confirmation));
            const response = await fetch(document.querySelector('[data-confirmation-status-url]').dataset.confirmationStatusUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': form.elements.csrfmiddlewaretoken.value },
                body,
            });
            if (!response.ok) return;
            const data = await response.json();
            cells.forEach(cell => {
                const confirmedAt = data.people[cell.dataset.confirmation];
                if (confirmedAt) cell.innerHTML = '<strong class="state-sent">ยืนยันแล้ว</strong><small></small>';
                if (confirmedAt) cell.querySelector('small').textContent = confirmedAt;
            });
        } catch (_) {
            // The next visibility change or polling interval retries quietly.
        }
    }
    document.addEventListener('visibilitychange', refreshConfirmations);
    window.setInterval(refreshConfirmations, 15000);
    sync(); runQueue(); refreshConfirmations();
})();
