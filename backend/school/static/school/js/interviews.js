(() => {
    const form = document.querySelector('#schedule-form');
    const boxes = [...form.querySelectorAll('[name="people"]')];
    const selectAll = document.querySelector('#select-all');
    const submit = document.querySelector('#confirm-schedule');
    const slotRows = document.querySelector('[data-slot-rows]');
    const slotTotal = document.querySelector('[data-slot-total]');
    const slotCapacityValue = document.querySelector('[data-slot-capacity-value]');
    let busy = false;
    let eventClosed = false;
    function addMinutes(value, minutes) {
        if (!value) return '';
        const [hour, minute] = value.split(':').map(Number);
        if (Number.isNaN(hour) || Number.isNaN(minute)) return '';
        const total = hour * 60 + minute + minutes;
        const nextHour = Math.floor((total % 1440) / 60).toString().padStart(2, '0');
        const nextMinute = (total % 60).toString().padStart(2, '0');
        return `${nextHour}:${nextMinute}`;
    }
    function renumberSlots() {
        if (!slotRows) return;
        [...slotRows.querySelectorAll('.slot-row')].forEach((row, index) => {
            row.querySelector('.slot-index').textContent = index + 1;
        });
    }
    function syncSlotTotal() {
        if (!slotRows || !slotTotal) return;
        const capacities = [...slotRows.querySelectorAll('[name="slot_capacity"]')].map(input => parseInt(input.value, 10) || 0);
        const total = capacities.reduce((sum, value) => sum + value, 0);
        const filledSlots = capacities.filter(Boolean).length;
        slotTotal.textContent = `รับรวม ${total} คน จาก ${filledSlots} slot`;
        if (slotCapacityValue) slotCapacityValue.textContent = total;
        renumberSlots();
    }
    function sync() {
        const count = boxes.filter(box => box.checked).length;
        const selectedCount = document.querySelector('#selected-count');
        if (selectedCount) selectedCount.textContent = count;
        if (submit) submit.disabled = busy || eventClosed || count === 0;
        if (selectAll) {
            selectAll.checked = count > 0 && count === boxes.length;
            selectAll.indeterminate = count > 0 && count < boxes.length;
        }
        syncSlotTotal();
    }
    function createSlotRow() {
        const lastRow = slotRows?.querySelector('.slot-row:last-child');
        const lastEnd = lastRow?.querySelector('[name="slot_end"]')?.value || '';
        const lastCapacity = lastRow?.querySelector('[name="slot_capacity"]')?.value || '';
        const nextEnd = addMinutes(lastEnd, 120);
        const row = document.createElement('div');
        row.className = 'slot-row';
        row.innerHTML = [
            '<span class="slot-index"></span>',
            `<label><span>เริ่มต้น</span><input type="time" name="slot_start" value="${lastEnd}"></label>`,
            `<label><span>สิ้นสุด</span><input type="time" name="slot_end" value="${nextEnd}"></label>`,
            `<label><span>รับได้</span><input type="number" min="1" name="slot_capacity" value="${lastCapacity}"></label>`,
            '<button type="button" class="slot-remove" data-remove-slot aria-label="ลบ slot">ลบ</button>',
        ].join('');
        return row;
    }
    document.querySelector('[data-add-slot]')?.addEventListener('click', () => {
        slotRows.appendChild(createSlotRow());
        syncSlotTotal();
    });
    slotRows?.addEventListener('input', syncSlotTotal);
    slotRows?.addEventListener('click', event => {
        const button = event.target.closest('[data-remove-slot]');
        if (!button) return;
        const rows = [...slotRows.querySelectorAll('.slot-row')];
        if (rows.length <= 1) {
            rows[0].querySelectorAll('input').forEach(input => { input.value = ''; });
        } else {
            button.closest('.slot-row').remove();
        }
        syncSlotTotal();
    });
    boxes.forEach(box => box.addEventListener('change', sync));
    selectAll?.addEventListener('change', () => { boxes.forEach(box => { box.checked = selectAll.checked; }); sync(); });
    form.addEventListener('submit', event => {
        const count = boxes.filter(box => box.checked).length;
        const typeLabel = form.dataset.typeLabel || 'นัดหมาย';
        const eventTitle = form.dataset.eventTitle;
        const eventLabel = eventTitle
            ? `เพิ่ม ${count} คนเข้า Event “${eventTitle}” และส่ง LINE`
            : `สร้าง Event ${typeLabel} วันที่ ${form.elements.date.value} สำหรับ ${count} คน และส่ง LINE`;
        if (busy || !window.confirm(`${eventLabel} ใช่หรือไม่?`)) event.preventDefault();
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
        const queueElement = document.querySelector('#interview-queue');
        if (!queueElement) return;
        const queue = JSON.parse(queueElement.textContent);
        if (!queue.length) return;
        busy = true; sync();
        const summary = document.querySelector('#send-summary'); summary.hidden = false;
        let sent = 0;
        for (let index = 0; index < queue.length; index++) {
            summary.textContent = `กำลังแจ้ง LINE ${index + 1}/${queue.length}`;
            if (await send(queue[index])) sent++;
        }
        summary.textContent = `บันทึกนัดแล้ว ${queue.length} คน · LINE รับข้อความแล้ว ${sent} คน · ส่งไม่สำเร็จ ${queue.length - sent} คน`;
        busy = false; sync(); refreshConfirmations();
    }
    async function refreshConfirmations() {
        const cells = [...document.querySelectorAll('[data-confirmation]')];
        const statusEndpoint = document.querySelector('[data-confirmation-status-url]');
        if ((!cells.length && !statusEndpoint?.dataset.eventId) || document.hidden) return;
        try {
            const body = new URLSearchParams();
            cells.forEach(cell => body.append('participants', cell.dataset.confirmation));
            if (statusEndpoint.dataset.eventId) body.set('event_id', statusEndpoint.dataset.eventId);
            const response = await fetch(statusEndpoint.dataset.confirmationStatusUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': form.elements.csrfmiddlewaretoken.value },
                body,
            });
            if (!response.ok) return;
            const data = await response.json();
            cells.forEach(cell => {
                const item = data.participants[cell.dataset.confirmation];
                if (item && item.status === 'confirmed') {
                    cell.innerHTML = '<strong class="state-sent">ยืนยันแล้ว</strong><small></small>';
                    cell.querySelector('small').textContent = item.confirmed_at;
                }
            });
            if (data.event?.capacity) {
                const countLabel = `${data.event.confirmed_count}/${data.event.capacity}`;
                document.querySelectorAll('[data-event-confirmed], [data-event-card-count], [data-event-full-count]').forEach(element => {
                    element.textContent = countLabel;
                });
                const progress = document.querySelector('[data-event-progress]');
                if (progress) progress.value = data.event.confirmed_count;
                if (data.event.is_full) {
                    eventClosed = true;
                    document.querySelector('[data-selected-event-card]')?.classList.add('full');
                    const state = document.querySelector('[data-event-state]');
                    if (state) state.textContent = 'เต็มแล้ว';
                    const message = document.querySelector('[data-event-full-message]');
                    if (message) message.hidden = false;
                    boxes.forEach(box => { box.checked = false; box.disabled = true; });
                    if (selectAll) selectAll.disabled = true;
                    document.querySelectorAll('[data-notify]').forEach(button => { button.disabled = true; });
                    sync();
                }
            }
            if (data.event) {
                const eventSent = document.querySelector('[data-event-sent]');
                const eventFailed = document.querySelector('[data-event-failed]');
                const audienceSent = document.querySelector('[data-audience-sent]');
                const audienceFailed = document.querySelector('[data-audience-failed]');
                if (eventSent) eventSent.textContent = data.event.sent_count;
                if (eventFailed) eventFailed.textContent = data.event.failed_count;
                if (audienceSent) audienceSent.textContent = data.event.invited_count;
                if (audienceFailed) audienceFailed.textContent = data.event.failed_count;
            }
        } catch (_) {
            // The next visibility change or polling interval retries quietly.
        }
    }
    document.addEventListener('visibilitychange', refreshConfirmations);
    window.setInterval(refreshConfirmations, 15000);
    sync(); runQueue(); refreshConfirmations();
})();
