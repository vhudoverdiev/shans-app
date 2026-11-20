(() => {
    const form = document.getElementById('contract-form');
    if (!form) return;
    const packages = JSON.parse(document.getElementById('contract-packages').textContent);
    const field = name => form.elements.namedItem(name);
    const set = (name, value) => { field(name).value = value; field(name).dispatchEvent(new Event('change', {bubbles:true})); };
    const note = document.getElementById('contract-package-note');
    function syncPrice() {
        const selected = packages.find(item => item.id === field('package').value);
        const hours = Number(field('hours').value.replace(',', '.'));
        if (!selected || !Number.isFinite(hours) || hours <= 0 || hours > 24) {
            field('price').value = '';
            return;
        }
        const rate = hours >= 2 ? 5000 : (selected.price ?? selected.hourly);
        field('price').value = Number.isFinite(rate) ? String(Math.round(rate * hours * 100) / 100) : '';
    }
    function syncKind() {
        const kind = field('kind').value;
        [['[data-contract-photo]', kind !== 'video'], ['[data-contract-video]', kind !== 'photo']].forEach(([selector, visible]) => {
            const section = form.querySelector(selector);
            section.hidden = !visible;
            section.querySelectorAll('input,textarea').forEach(input => {
                input.required = visible && input.name !== 'video_extras';
                input.disabled = !visible;
            });
        });
    }
    function syncTime() {
        const start = field('start_time').value;
        const hours = Number(field('hours').value.replace(',', '.'));
        if (!start || !Number.isFinite(hours) || hours <= 0 || hours > 24) return;
        const [h,m] = start.split(':').map(Number);
        const minutes = (h*60 + m + Math.round(hours*60)) % 1440;
        field('end_time').value = `${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')}`;
    }
    document.getElementById('contract-apply-package').addEventListener('click', () => {
        const selected = packages.find(item => item.id === field('package').value);
        if (!selected) return;
        set('kind', selected.kind); set('subject', selected.title);
        const hours = Number(field('hours').value.replace(',', '.'));
        syncPrice();
        set('photo_count', selected.photos ? Math.floor(selected.photos * (selected.hourly && hours > 0 ? hours : 1)) : '');
        set('retouch_count', selected.retouch ?? '');
        set('photo_format', 'JPEG');
        set('video_format', 'MOV или MP4');
        set('wishes', selected.extras || 'нет');
        set('studio', selected.studio ? 'separate' : 'none');
        set('studio_details', selected.studio ? '' : 'не применимо');
        note.textContent = 'Пакет применён.';
        syncKind(); syncTime();
    });
    field('hours').addEventListener('input', () => { syncPrice(); syncTime(); });
    field('package').addEventListener('change', syncPrice);
    field('delivery_days').addEventListener('input', () => {
        const summary = document.getElementById('contract-delivery-summary');
        if (summary) summary.textContent = field('delivery_days').value ? `до ${field('delivery_days').value} дн.` : '—';
    });
    field('kind').addEventListener('change', syncKind);
    ['start_time','hours'].forEach(name => field(name).addEventListener('change', syncTime));
    syncKind();
})();
