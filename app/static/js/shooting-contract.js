(() => {
    const form = document.getElementById('contract-form');
    if (!form) return;
    const packages = JSON.parse(document.getElementById('contract-packages').textContent);
    const field = name => form.elements.namedItem(name);
    const set = (name, value) => { field(name).value = value; field(name).dispatchEvent(new Event('change', {bubbles:true})); };
    const note = document.getElementById('contract-package-note');
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
        if (selected.hours) set('hours', selected.hours);
        const hours = Number(field('hours').value.replace(',', '.'));
        const price = selected.hourly ? (selected.id === 'brand' ? selected.hourly*hours : hours >= 2 ? selected.hourly*hours : 6000) : selected.price;
        set('price', Number.isFinite(price) ? price : '');
        set('photo_count', selected.photos ? Math.floor(selected.photos * (selected.hourly && hours > 0 ? hours : 1)) : '');
        set('retouch_count', selected.retouch ?? '');
        set('photo_format', 'JPEG');
        set('wishes', selected.extras || 'нет');
        set('studio', selected.studio ? 'separate' : 'none');
        set('studio_details', selected.studio ? '' : 'не применимо');
        note.textContent = selected.studio ? `Цена услуг: ${selected.price.toLocaleString('ru-RU')} ₽${selected.from_price ? ' (от)' : ''}. Из прайса ${selected.public_price.toLocaleString('ru-RU')} ₽ вычтено 2 500 ₽ за студию — заказчик оплачивает её отдельно.` : `${selected.from_price ? 'Цена — ориентир «от», уточните итоговую сумму. ' : ''}Пакет применён. Уточните результат, технические параметры и объём корректировок.`;
        syncKind(); syncTime();
    });
    field('kind').addEventListener('change', syncKind);
    ['start_time','hours'].forEach(name => field(name).addEventListener('change', syncTime));
    syncKind();
})();
