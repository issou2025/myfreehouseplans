// Lightweight UI enhancements for the filter panel and chips
(function(){
    const panel = document.getElementById('filterPanel');
    const toggle = document.querySelector('.filters-toggle');
    if(!panel || !toggle) return;

    // Accessibility helpers
    function openPanel(){
        panel.classList.add('is-open');
        toggle.setAttribute('aria-expanded','true');
        // trap focus minimally
        document.body.style.overflow = 'hidden';
        panel.querySelectorAll('input,select,button,textarea')[0]?.focus();
    }
    function closePanel(){
        panel.classList.remove('is-open');
        toggle.setAttribute('aria-expanded','false');
        document.body.style.overflow = '';
        toggle.focus();
    }

    toggle.addEventListener('click', function(){
        const open = panel.classList.contains('is-open');
        if(open) closePanel(); else openPanel();
    });

    // Close on Escape
    document.addEventListener('keydown', function(e){
        if(e.key === 'Escape' && panel.classList.contains('is-open')){
            closePanel();
        }
    });

    // Chip micro-interaction: gentle scale and color ripple handled by CSS class toggles.
    document.addEventListener('click', function(e){
        const chip = e.target.closest('.narrative-chip');
        if(!chip) return;
        chip.classList.add('chip-pressed');
        setTimeout(()=> chip.classList.remove('chip-pressed'), 240);
    });

    // Make narrative chips keyboard friendly (space/enter)
    document.querySelectorAll('.narrative-chip').forEach(ch => {
        ch.setAttribute('tabindex', '0');
        ch.addEventListener('keydown', function(e){
            if(e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                ch.click();
            }
        });
    });

    // Small visual feedback when results update (listen to plan fetch events)
    document.addEventListener('DOMContentLoaded', ()=>{
        const form = document.querySelector('[data-plan-browser]');
        if(!form) return;
        const observer = new MutationObserver(()=>{
            // flash little pulse on grid
            const grid = document.getElementById('planGrid');
            if(!grid) return;
            grid.classList.add('results-updated');
            setTimeout(()=> grid.classList.remove('results-updated'), 520);
        });
        const grid = document.getElementById('planGrid');
        if(grid) observer.observe(grid, { childList: true, subtree: false });
    });
})();
