(() => {
    const form = document.querySelector('#schedule-form');
    const boxes = [...form.querySelectorAll('[name="people"]')];
    const selectAll = document.querySelector('#select-all');
    const submit = document.querySelector('#confirm-schedule');
    const slotRows = document.querySelector('[data-slot-rows]');
    const slotTotal = document.querySelector('[data-slot-total]');
    let busy = false;
    function syncSlotTotal() {
        if (!slotRows || !slotTotal) return;
        const total = [...slotRows.querySelectorAll('[name="slot_capacity"]')].reduce((sum, input) => sum + (parseInt(input.value, 10) || 0), 0);
        const target = parseInt(form.elements.total_capacity?.value || '0', 10) || 0;
        slotTotal.textContent = `ผลรวม quota slot: ${total} คน${target ? ` / จำนวนรับรวม ${target} คน` : ''}`;
        slotTotal.classList.toggle('mismatch', !!target && total !== target);
    }
    function sync() {
        const count = boxes.filter(box => box.checked).length;
        document.querySelector('#selected-count').textContent = count;
        submit.disabled = busy || count === 0;
        selectAll.checked = count > 0 && count === boxes.length;
        selectAll.indeterminate = count > 0 && count < boxes.length;
        syncSlotTotal();
    }
    function createSlotRow() {
        const row = document.createElement('div');
        row.className = 'slot-row';
        row.innerHTML = [
            '<label><span>เริ่ม</span><input type="time" name="slot_start"></label>',
            '<label><span>สิ้นสุด</span><input type="time" name="slot_end"></label>',
            '<label><span>Quota</span><input type="number" min="1" name="slot_capacity"></label>',
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
    form.elements.total_capacity?.addEventListener('input', syncSlotTotal);
    boxes.forEach(box => box.addEventListener('change', sync));
    selectAll.addEventListener('change', () => { boxes.forEach(box => { box.checked = selectAll.checked; }); sync(); });
    form.addEventListener('submit', event => {
        const count = boxes.filter(box => box.checked).length;
        const typeLabel = form.dataset.typeLabel || 'นัดหมาย';
        const slotLabel = slotRows ? `วันที่ ${form.elements.date.value} ตาม slot ที่กำหนด` : `วันที่ ${form.elements.date.value} เวลา ${form.elements.time.value} (ประเทศไทย)`;
        if (busy || !window.confirm(`สร้างนัด${typeLabel}สำหรับ ${count} คน ${slotLabel} และส่ง LINE ใช่หรือไม่?`)) event.preventDefault();
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
            cells.forEach(cell => body.append('participants', cell.dataset.confirmation));
            const response = await fetch(document.querySelector('[data-confirmation-status-url]').dataset.confirmationStatusUrl, {
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
        } catch (_) {
            // The next visibility change or polling interval retries quietly.
        }
    }
    document.addEventListener('visibilitychange', refreshConfirmations);
    window.setInterval(refreshConfirmations, 15000);
    sync(); runQueue(); refreshConfirmations();
})();
