(() => {
    document.querySelectorAll('[data-student-upload-form]').forEach(form => {
        const input = form.querySelector('[data-student-upload-input]');
        const label = form.querySelector('[data-student-file-label]');
        if (!input || !label) return;
        input.addEventListener('change', () => {
            const file = input.files && input.files[0];
            label.textContent = file ? file.name : 'เลือกไฟล์การบ้าน';
        });
    });
})();
