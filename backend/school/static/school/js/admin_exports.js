(() => {
    "use strict";
    const slotData = JSON.parse(document.querySelector('#export-interview-slots')?.textContent || '{}');

    function refreshSlots(eventSelect, keepSelection = false) {
        const form = eventSelect.closest('form');
        const slotSelect = form?.querySelector('[data-slot-select]');
        const modeSelect = form?.querySelector('[data-mode-select]');
        if (!slotSelect) return;
        const eventId = eventSelect.value;
        const slots = slotData[eventId] || [];
        const selectedSlot = keepSelection ? slotSelect.dataset.selectedSlot : '';
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
            option.selected = String(slot.id) === selectedSlot;
            slotSelect.append(option);
        });
        slotSelect.disabled = !eventId || slots.length === 0;
        if (modeSelect) {
            modeSelect.disabled = !eventId;
            if (!eventId) modeSelect.value = '';
        }
    }

    document.querySelectorAll('[data-slot-event]').forEach(eventSelect => {
        eventSelect.addEventListener('change', () => refreshSlots(eventSelect, false));
        refreshSlots(eventSelect, true);
    });
})();
