(() => {
    "use strict";
    const eventSelect = document.querySelector('[data-export-event]');
    const slotSelect = document.querySelector('[data-export-slot]');
    const slotData = JSON.parse(document.querySelector('#export-interview-slots')?.textContent || '{}');

    function refreshSlots() {
        if (!eventSelect || !slotSelect) return;
        const eventId = eventSelect.value;
        const slots = slotData[eventId] || [];
        slotSelect.replaceChildren();
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = !eventId
            ? 'เลือกกิจกรรมก่อน'
            : slots.length
                ? 'ทุกช่วงเวลา'
                : 'กิจกรรมนี้ไม่มี Slot';
        slotSelect.append(defaultOption);
        slots.forEach(slot => {
            const option = document.createElement('option');
            option.value = String(slot.id);
            option.textContent = slot.label;
            slotSelect.append(option);
        });
        slotSelect.disabled = !eventId || slots.length === 0;
    }

    eventSelect?.addEventListener('change', refreshSlots);
    refreshSlots();
})();
