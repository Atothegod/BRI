(() => {
    const form = document.querySelector('[data-teacher-calendar-form]');
    if (!form) return;

    const boxes = [...form.querySelectorAll('input[name="students"]')];
    const submit = form.querySelector('.teacher-calendar-submit');
    const selectVisible = form.querySelector('[data-select-visible-students]');
    const dateInput = form.elements.date;
    const timeInput = form.elements.time;
    const csrfToken = form.elements.csrfmiddlewaretoken.value;
    const queueElement = document.querySelector('#teacher-appointment-queue');
    const notifyTemplate = document.querySelector('[data-notify-url-template]')?.dataset.notifyUrlTemplate || '';
    let busy = false;

    function pad(value) {
        return String(value).padStart(2, '0');
    }

    function setInitialDateTime() {
        const now = new Date();
        now.setMinutes(now.getMinutes() + 60);
        if (!dateInput.value) {
            dateInput.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        }
        if (!timeInput.value) {
            timeInput.value = `${pad(now.getHours())}:00`;
        }
    }

    function selectedCount() {
        return boxes.filter(box => box.checked).length;
    }

    function sync() {
        const count = selectedCount();
        submit.disabled = busy || count === 0;
        submit.querySelector('span').textContent = count > 0
            ? `สร้างนัดและส่ง LINE (${count})`
            : 'สร้างนัดและส่ง LINE';
    }

    boxes.forEach(box => box.addEventListener('change', sync));
    selectVisible?.addEventListener('click', () => {
        const shouldCheck = selectedCount() !== boxes.length;
        boxes.forEach(box => {
            box.checked = shouldCheck;
        });
        selectVisible.textContent = shouldCheck ? 'ล้างที่เลือก' : 'เลือกทั้งหมด';
        sync();
    });

    form.addEventListener('submit', event => {
        const count = selectedCount();
        if (!count || busy) {
            event.preventDefault();
            return;
        }
        const date = dateInput.value;
        const time = timeInput.value;
        if (!window.confirm(`สร้างนัดเรียนวันที่ ${date} เวลา ${time} และส่ง LINE ให้ ${count} คน ใช่หรือไม่?`)) {
            event.preventDefault();
            return;
        }
        busy = true;
        sync();
    });

    async function notifyParticipant(item) {
        const url = item.url || notifyTemplate.replace('/0/', `/${item.id}/`);
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: new URLSearchParams({ at: item.at }),
            });
            const data = await response.json();
            return !!data.sent;
        } catch (_) {
            return false;
        }
    }

    async function runQueue() {
        if (!queueElement) return;
        const queue = JSON.parse(queueElement.textContent || '[]');
        if (!queue.length) return;
        const summary = document.querySelector('#teacher-send-summary');
        summary.hidden = false;
        busy = true;
        sync();
        let sent = 0;
        for (let index = 0; index < queue.length; index += 1) {
            summary.textContent = `กำลังส่ง LINE ${index + 1}/${queue.length}`;
            if (await notifyParticipant(queue[index])) sent += 1;
        }
        summary.textContent = `บันทึกนัดแล้ว ${queue.length} คน · LINE รับข้อความแล้ว ${sent} คน · ส่งไม่สำเร็จ ${queue.length - sent} คน`;
        busy = false;
        sync();
    }

    setInitialDateTime();
    sync();
    runQueue();
})();
