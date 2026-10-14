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

    const applicantBoxes = [...document.querySelectorAll('.export-person-picker input[name="people"]')];
    const selectAllApplicants = document.querySelector('[data-select-all-applicants]');
    const selectedApplicantCount = document.querySelector('[data-selected-applicant-count]');
    const openSelected = document.querySelector('[data-open-selected]');

    function syncApplicantSelection() {
        const selected = applicantBoxes.filter(box => box.checked).length;
        if (selectedApplicantCount) selectedApplicantCount.textContent = selected.toLocaleString('th-TH');
        if (openSelected) openSelected.disabled = selected === 0;
        if (selectAllApplicants) {
            selectAllApplicants.checked = applicantBoxes.length > 0 && selected === applicantBoxes.length;
            selectAllApplicants.indeterminate = selected > 0 && selected < applicantBoxes.length;
        }
    }

    applicantBoxes.forEach(box => box.addEventListener('change', syncApplicantSelection));
    selectAllApplicants?.addEventListener('change', () => {
        applicantBoxes.forEach(box => { box.checked = selectAllApplicants.checked; });
        syncApplicantSelection();
    });
    syncApplicantSelection();
})();
