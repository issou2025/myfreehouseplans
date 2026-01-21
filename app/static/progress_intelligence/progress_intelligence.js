(function () {
  const unitSelect = document.getElementById('surface_unit');
  const areaInput = document.getElementById('surface_area');
  const hint = document.getElementById('area_hint');

  if (!unitSelect || !areaInput || !hint) return;

  const FT2_PER_M2 = 10.7639;

  function toM2(v, unit) {
    const n = Number(v);
    if (!Number.isFinite(n)) return null;
    return unit === 'ft2' ? n / FT2_PER_M2 : n;
  }

  function fromM2(m2, unit) {
    return unit === 'ft2' ? m2 * FT2_PER_M2 : m2;
  }

  function format(n) {
    return Math.round(n).toString();
  }

  function updateHint() {
    const unit = unitSelect.value;
    const value = areaInput.value;
    const m2 = toM2(value, unit);
    if (m2 === null) {
      hint.textContent = '';
      return;
    }

    const otherUnit = unit === 'm2' ? 'ft2' : 'm2';
    const converted = fromM2(m2, otherUnit);
    hint.textContent = `≈ ${format(converted)} ${otherUnit === 'm2' ? 'm²' : 'ft²'}`;
  }

  unitSelect.addEventListener('change', updateHint);
  areaInput.addEventListener('input', updateHint);
  updateHint();
})();
