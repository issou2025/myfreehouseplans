// Minimal progressive enhancement for the catalog "Load more" experience.

(function () {
	function buildFragmentUrl(fragmentBase, nextPage) {
		const url = new URL(fragmentBase, window.location.origin);
		const params = new URLSearchParams(window.location.search);
		params.set('page', String(nextPage));
		url.search = params.toString();
		return url.toString();
	}
	async function loadMorePlans() {
		const grid = document.getElementById('planGrid');
		const btn = document.getElementById('loadMorePlans');
		if (!grid || !btn) return;

		const fragmentUrl = grid.dataset.fragmentUrl;
		const nextPageRaw = grid.dataset.nextPage;
		const nextPage = parseInt(nextPageRaw || '', 10);

		if (!fragmentUrl || !nextPage || Number.isNaN(nextPage)) {
			btn.disabled = true;
			return;
		}

		btn.disabled = true;
		const prevText = btn.textContent;
		btn.textContent = 'Loading…';

		try {
			const url = buildFragmentUrl(fragmentUrl, nextPage);
			const resp = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } });
			if (!resp.ok) throw new Error('Failed to load more plans');

			const html = await resp.text();
			if (html) {
				grid.insertAdjacentHTML('beforeend', html);
				const refreshEvt = new CustomEvent('favorites:refresh');
				document.dispatchEvent(refreshEvt);
				document.dispatchEvent(new CustomEvent('compare:refresh'));
			}

			const hasNext = resp.headers.get('X-Has-Next');
			const nextFromHeader = resp.headers.get('X-Next-Page');
			if (hasNext === '1' && nextFromHeader) {
				grid.dataset.nextPage = nextFromHeader;
				btn.disabled = false;
				btn.textContent = prevText;
			} else {
				btn.remove();
			}
		} catch (err) {
			btn.disabled = false;
			btn.textContent = prevText;
		}
	}

	document.addEventListener('click', function (e) {
		const target = e.target;
		if (!(target instanceof HTMLElement)) return;
		if (target.id !== 'loadMorePlans') return;
		e.preventDefault();
		loadMorePlans();
	});
})();

// Image skeleton handling: hide skeleton overlay when images load (prevents CLS)
document.addEventListener('DOMContentLoaded', function () {
	function bindImage(img) {
		try {
			const parent = img.closest('.plan-card__media');
			if (!parent) return;
			if (img.complete && img.naturalWidth > 0) {
				parent.classList.add('is-loaded');
				return;
			}
			img.addEventListener('load', function () { parent.classList.add('is-loaded'); });
			img.addEventListener('error', function () { parent.classList.add('is-loaded'); });
		} catch (e) {
			// Defensive: never throw in UI enhancement
			console.warn('bindImage error', e);
		}
	}

	document.querySelectorAll('img.js-lazy-img').forEach(bindImage);

	// Handle images added via fetch (infinite scroll / load more)
	const grid = document.getElementById('planGrid');
	if (grid && window.MutationObserver) {
		const mo = new MutationObserver(function (mutations) {
			mutations.forEach(function (m) {
				m.addedNodes.forEach(function (n) {
					if (!(n instanceof HTMLElement)) return;
					n.querySelectorAll && n.querySelectorAll('img.js-lazy-img').forEach(bindImage);
				});
			});
		});
		mo.observe(grid, { childList: true, subtree: true });
	}
});

// FAQ accordion progressive enhancement
document.addEventListener('DOMContentLoaded', function () {
	try {
		const list = document.getElementById('faq-list');
		if (!list) return;
		list.querySelectorAll('.faq-item').forEach(function (item) {
			const btn = item.querySelector('.faq-question');
			const answer = item.querySelector('.faq-answer');
			if (!btn || !answer) return;
			// Initialize accessibility attributes
			btn.setAttribute('aria-expanded', 'false');
			answer.hidden = true;
			btn.addEventListener('click', function () {
				const expanded = btn.getAttribute('aria-expanded') === 'true';
				btn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
				if (expanded) {
					answer.hidden = true;
				} else {
					answer.hidden = false;
				}
			});
		});
	} catch (e) {
		console.warn('FAQ enhancement failed', e);
	}
});

// Toast notifications (Flash messages) ------------------------------------
document.addEventListener('DOMContentLoaded', function () {
	try {
		const toasts = Array.from(document.querySelectorAll('.toast'));
		if (!toasts.length) return;

		function dismissToast(toast) {
			if (!toast || toast.classList.contains('is-hiding')) return;
			toast.classList.add('is-hiding');
			toast.classList.remove('is-visible');
			toast.addEventListener(
				'transitionend',
				function () {
					toast.remove();
				},
				{ once: true }
			);
			// Fallback removal in case transitionend doesn't fire.
			setTimeout(function () {
				try { toast.remove(); } catch (e) {}
			}, 700);
		}

		toasts.forEach(function (toast) {
			// Animate in.
			requestAnimationFrame(function () {
				toast.classList.add('is-visible');
			});

			// Manual close.
			const closeBtn = toast.querySelector('.toast__close');
			if (closeBtn) {
				closeBtn.addEventListener('click', function () {
					dismissToast(toast);
				});
			}

			// Auto-dismiss.
			const timeoutMs = parseInt(toast.getAttribute('data-timeout') || '4000', 10);
			if (!Number.isNaN(timeoutMs) && timeoutMs > 0) {
				setTimeout(function () {
					dismissToast(toast);
				}, timeoutMs);
			}
		});
	} catch (e) {
		console.warn('Toast enhancement failed', e);
	}
});

// Catalog filters + real-time search ------------------------------------
(function () {
	const form = document.querySelector('[data-plan-browser]');
	const grid = document.getElementById('planGrid');
	const emptyState = document.getElementById('planEmptyState');
	const summaryEl = document.querySelector('[data-results-summary]');
	const paginationWrapper = document.querySelector('[data-pagination-wrapper]');
	const loadMoreWrapper = document.querySelector('[data-load-more-wrapper]');
	const loadMoreBtn = document.getElementById('loadMorePlans');
	const loadMoreTerminal = loadMoreWrapper ? loadMoreWrapper.querySelector('[data-load-more-terminal]') : null;
	const narrativeInput = form.querySelector('[data-narrative-input]');
	const narrativeChips = Array.from(document.querySelectorAll('[data-narrative-trigger]'));
	const narrativeHelper = form.querySelector('[data-narrative-helper]');
	const narrativeHelperDefault = narrativeHelper ? narrativeHelper.textContent : '';

	if (!form || !grid) return;

	let debounceTimer = null;
	let controller = null;

	function setLoading(isLoading) {
		form.classList.toggle('is-loading', Boolean(isLoading));
		form.setAttribute('aria-busy', isLoading ? 'true' : 'false');
	}

	function serializeForm(targetForm) {
		const data = new FormData(targetForm);
		const params = new URLSearchParams();
		data.forEach((value, key) => {
			if (value instanceof File) return;
			if (typeof value === 'string') {
				const trimmed = value.trim();
				if (trimmed === '') return;
				params.append(key, trimmed);
				return;
			}
			if (value !== null && value !== undefined) {
				params.append(key, value);
			}
		});
		return params;
	}

	function updateHistory(params) {
		const query = params.toString();
		const newUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
		window.history.replaceState({}, '', newUrl);
	}

	function syncLoadMore(payload) {
		grid.dataset.nextPage = payload.nextPage ? String(payload.nextPage) : '';
		if (loadMoreBtn) {
			const hasNext = Boolean(payload.hasNext);
			loadMoreBtn.hidden = !hasNext;
			loadMoreBtn.disabled = !hasNext;
			if (hasNext) {
				loadMoreBtn.textContent = 'Load more plans';
			}
		}
		if (loadMoreTerminal) {
			const shouldShowTerminal = !payload.hasNext && payload.hasResults;
			loadMoreTerminal.hidden = !shouldShowTerminal;
		}
	}

	function syncSummary(payload) {
		if (summaryEl) {
			summaryEl.textContent = payload.summaryText || `${payload.total || 0} plans available`;
		}
		if (emptyState) {
			emptyState.hidden = Boolean(payload.hasResults);
			if (!payload.hasResults) {
				emptyState.setAttribute('aria-live', 'polite');
			}
		}
	}

	function refreshEnhancements() {
		document.dispatchEvent(new CustomEvent('favorites:refresh'));
		document.dispatchEvent(new CustomEvent('compare:refresh'));
	}

	async function fetchPlans(params) {
		if (controller) {
			controller.abort();
		}
		controller = new AbortController();
		setLoading(true);
		try {
			const resp = await fetch(`/plans/data?${params.toString()}`, {
				headers: { 'X-Requested-With': 'fetch' },
				signal: controller.signal,
			});
			if (!resp.ok) throw new Error('Filters request failed');
			const payload = await resp.json();
			grid.innerHTML = payload.cardsHtml || '';
			if (paginationWrapper) {
				paginationWrapper.innerHTML = payload.paginationHtml || '';
			}
			syncSummary(payload);
			syncLoadMore(payload);
			refreshEnhancements();
			updateHistory(params);
		} catch (error) {
			if (error.name !== 'AbortError') {
				console.error(error);
			}
		} finally {
			setLoading(false);
		}
	}

	function requestUpdate(overrides = {}) {
		const params = serializeForm(form);
		params.delete('page');
		Object.keys(overrides).forEach((key) => {
			const value = overrides[key];
			if (value === null || value === undefined || value === '') {
				params.delete(key);
			} else {
				params.set(key, value);
			}
		});
		fetchPlans(params);
	}

	function resetFilters() {
		form.querySelectorAll('input[type="text"], input[type="number"]').forEach((input) => {
			input.value = '';
		});
		form.querySelectorAll('select').forEach((select) => {
			select.selectedIndex = 0;
		});
		if (narrativeInput) {
			narrativeInput.value = '';
			updateNarrativeChips('');
		}
		requestUpdate();
	}

	function updateNarrativeChips(activeValue) {
		narrativeChips.forEach((chip) => {
			const value = chip.getAttribute('data-value');
			const isActive = activeValue && activeValue === value;
			chip.classList.toggle('is-active', Boolean(isActive));
			chip.setAttribute('aria-pressed', String(Boolean(isActive)));
		});
		if (narrativeHelper) {
			const activeChip = narrativeChips.find((chip) => chip.getAttribute('data-value') === activeValue);
			const helperText = activeChip ? activeChip.getAttribute('data-helper') || narrativeHelperDefault : narrativeHelperDefault;
			narrativeHelper.textContent = helperText || narrativeHelperDefault;
		}
	}

	form.addEventListener('change', (event) => {
		if (event.target instanceof HTMLSelectElement) {
			requestUpdate();
		}
	});

	form.addEventListener('submit', (event) => {
		event.preventDefault();
		requestUpdate();
	});

	const searchInput = form.querySelector('input[name="q"]');
	if (searchInput) {
		searchInput.addEventListener('input', () => {
			clearTimeout(debounceTimer);
			debounceTimer = window.setTimeout(() => {
				requestUpdate();
			}, 300);
		});
	}

	document.addEventListener('click', (event) => {
		const link = event.target instanceof HTMLElement ? event.target.closest('[data-pagination-link]') : null;
		if (!link) return;
		const paginationHost = link.closest('[data-pagination]');
		if (!paginationHost || !paginationWrapper || !paginationWrapper.contains(paginationHost)) return;
		event.preventDefault();
		const page = link.getAttribute('data-page');
		if (!page) return;
		const params = serializeForm(form);
		params.set('page', page);
		fetchPlans(params);
	});

	document.addEventListener('click', (event) => {
		const resetBtn = event.target instanceof HTMLElement ? event.target.closest('[data-filters-reset]') : null;
		if (!resetBtn) return;
		event.preventDefault();
		resetFilters();
	});

	form.addEventListener('click', (event) => {
		const chip = event.target instanceof HTMLElement ? event.target.closest('[data-narrative-trigger]') : null;
		if (!chip || !narrativeInput) return;
		event.preventDefault();
		const value = chip.getAttribute('data-value') || '';
		const nextValue = narrativeInput.value === value ? '' : value;
		narrativeInput.value = nextValue;
		updateNarrativeChips(nextValue);
		requestUpdate();
	});

	updateNarrativeChips(narrativeInput ? narrativeInput.value : '');
})();

// Recently viewed + similar rails ---------------------------------------
(function () {
	const STORAGE_KEY = 'myfreehouseplan:recently-viewed';
	const MAX_ITEMS = 12;

	function hasStorage() {
		try {
			const testKey = '__recent_test__';
			localStorage.setItem(testKey, '1');
			localStorage.removeItem(testKey);
			return true;
		} catch (error) {
			return false;
		}
	}

	function readHistory() {
		if (!hasStorage()) return [];
		try {
			const raw = localStorage.getItem(STORAGE_KEY);
			if (!raw) return [];
			const parsed = JSON.parse(raw);
			return Array.isArray(parsed) ? parsed : [];
		} catch (error) {
			return [];
		}
	}

	function writeHistory(entries) {
		if (!hasStorage()) return;
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
		} catch (error) {
			console.warn('Unable to persist recently viewed history', error);
		}
	}

	function numberFromValue(value) {
		const numeric = Number(value);
		return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
	}

	function buildRailCard(plan) {
		const article = document.createElement('article');
		article.className = 'rail-card';

		const mediaLink = document.createElement('a');
		mediaLink.className = 'rail-card__media';
		mediaLink.href = `/plan/${plan.slug}`;
		mediaLink.setAttribute('aria-label', `View plan ${plan.title || plan.reference || ''}`.trim());
		if (plan.thumb) {
			const img = document.createElement('img');
			img.src = plan.thumb;
			img.alt = plan.title || 'House plan preview';
			img.loading = 'lazy';
			mediaLink.appendChild(img);
		} else {
			const placeholder = document.createElement('div');
			placeholder.className = 'rail-card__placeholder';
			placeholder.textContent = 'Preview coming soon';
			mediaLink.appendChild(placeholder);
		}

		const body = document.createElement('div');
		body.className = 'rail-card__body';

		const ref = document.createElement('p');
		ref.className = 'rail-card__ref';
		ref.textContent = `Ref ${plan.reference || '—'}`;
		body.appendChild(ref);

		const title = document.createElement('h3');
		title.className = 'rail-card__title';
		const titleLink = document.createElement('a');
		titleLink.href = `/plan/${plan.slug}`;
		titleLink.textContent = plan.title || 'View plan';
		title.appendChild(titleLink);
		body.appendChild(title);

		const metaParts = [];
		const areaValue = numberFromValue(plan.area);
		if (areaValue) {
			metaParts.push(`${Math.round(areaValue).toLocaleString()} sq ft`);
		}
		if (plan.bedrooms) {
			metaParts.push(`${plan.bedrooms} beds`);
		}
		if (metaParts.length) {
			const meta = document.createElement('p');
			meta.className = 'rail-card__meta';
			meta.textContent = metaParts.join(' · ');
			body.appendChild(meta);
		}

		const priceValue = numberFromValue(plan.starting_price || plan.price);
		if (priceValue) {
			const price = document.createElement('p');
			price.className = 'rail-card__price';
			price.textContent = `From $${Math.round(priceValue).toLocaleString()}`;
			body.appendChild(price);
		}

		article.appendChild(mediaLink);
		article.appendChild(body);
		return article;
	}

	function renderRecentlyViewed(history) {
		const grids = document.querySelectorAll('[data-recently-grid]');
		if (!grids.length) return;
		let hasRendered = false;
		grids.forEach((grid) => {
			const section = grid.closest('[data-recently-section]');
			const limitAttr = Number(grid.getAttribute('data-recently-limit') || '6');
			const limit = Number.isNaN(limitAttr) ? 6 : Math.max(1, limitAttr);
			grid.innerHTML = '';
			const items = history.slice(0, limit);
			if (!items.length) {
				if (section) {
					section.hidden = true;
					const emptyLabel = section.querySelector('[data-recently-empty]');
					if (emptyLabel) {
						emptyLabel.hidden = false;
					}
				}
				return;
			}
			const frag = document.createDocumentFragment();
			items.forEach((plan) => {
				const card = buildRailCard(plan);
				frag.appendChild(card);
			});
			grid.appendChild(frag);
			hasRendered = true;
			if (section) {
				section.hidden = false;
				const emptyLabel = section.querySelector('[data-recently-empty]');
				if (emptyLabel) {
					emptyLabel.hidden = true;
				}
			}
		});
		if (hasRendered) {
			document.dispatchEvent(new CustomEvent('favorites:refresh'));
			document.dispatchEvent(new CustomEvent('compare:refresh'));
		}
	}

	async function hydrateSimilarFromHistory(history) {
		const sections = Array.from(document.querySelectorAll('[data-similar-section][data-similar-source="history"]'));
		if (!sections.length) return;
		const head = history[0];
		if (!head || !head.slug) {
			sections.forEach((section) => {
				section.hidden = true;
			});
			return;
		}
		try {
			const resp = await fetch(`/plans/similar/${head.slug}?limit=6`, {
				headers: { 'X-Requested-With': 'fetch' },
			});
			if (!resp.ok) throw new Error('Failed to fetch similar plans');
			const payload = await resp.json();
			const plans = Array.isArray(payload.plans) ? payload.plans : [];
			sections.forEach((section) => {
				const grid = section.querySelector('[data-similar-grid]');
				if (!grid) return;
				grid.innerHTML = '';
				if (!plans.length) {
					section.hidden = true;
					return;
				}
				const frag = document.createDocumentFragment();
				plans.forEach((plan) => {
					const card = buildRailCard(plan);
					frag.appendChild(card);
				});
				grid.appendChild(frag);
				section.hidden = false;
			});
			if (plans.length) {
				document.dispatchEvent(new CustomEvent('favorites:refresh'));
				document.dispatchEvent(new CustomEvent('compare:refresh'));
			}
		} catch (error) {
			sections.forEach((section) => {
				section.hidden = true;
			});
		}
	}

	function trackCurrentPlan(history) {
		const tracker = document.querySelector('[data-plan-track]');
		if (!tracker || !hasStorage()) return history;
		const slug = tracker.getAttribute('data-plan-slug');
		if (!slug) return history;
		const entry = {
			slug,
			title: tracker.getAttribute('data-plan-title') || '',
			reference: tracker.getAttribute('data-plan-reference') || '',
			thumb: tracker.getAttribute('data-plan-thumb') || '',
			area: tracker.getAttribute('data-plan-area') || '',
			bedrooms: tracker.getAttribute('data-plan-bedrooms') || '',
			starting_price: tracker.getAttribute('data-plan-price') || '',
		};
		const filtered = history.filter((plan) => plan.slug !== slug);
		filtered.unshift(entry);
		const trimmed = filtered.slice(0, MAX_ITEMS);
		writeHistory(trimmed);
		return trimmed;
	}

	function init() {
		let history = readHistory();
		history = trackCurrentPlan(history);
		renderRecentlyViewed(history);
		hydrateSimilarFromHistory(history);
	}

	init();
})();

// Compare tray + table -----------------------------------------------
(function () {
	const STORAGE_KEY = 'myfreehouseplan:compare';
	const MAX_ITEMS = 3;
	const SPEC_ROWS = [
		{ key: 'price', label: 'Starting price', formatter: (plan) => formatPriceValue(plan) },
		{ key: 'area', label: 'Area', formatter: (plan) => formatArea(plan) },
		{ key: 'bedrooms', label: 'Bedrooms', formatter: (plan) => plan.bedrooms || '—' },
		{ key: 'bathrooms', label: 'Bathrooms', formatter: (plan) => plan.bathrooms || '—' },
		{ key: 'floors', label: 'Levels', formatter: (plan) => plan.floors || '—' },
		{ key: 'parking', label: 'Parking', formatter: (plan) => plan.parking || '—' },
		{ key: 'categories', label: 'Categories', formatter: (plan) => plan.categories || '—' },
		{ key: 'deliverables', label: 'Deliverables', formatter: (plan) => (plan.hasFree ? 'Includes free preview pack' : 'Paid packs only') },
	];
	let compareState = [];
	let limitNoticeTimer = 0;

	function hasStorage() {
		try {
			const key = '__compare_test__';
			localStorage.setItem(key, '1');
			localStorage.removeItem(key);
			return true;
		} catch (error) {
			return false;
		}
	}

	function toPositiveNumber(value) {
		if (value === null || value === undefined || value === '') return null;
		const numeric = Number(value);
		return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
	}

	function asBoolean(value) {
		if (value === true || value === 'true') return true;
		if (value === false || value === 'false') return false;
		if (value === 1 || value === '1') return true;
		if (value === 0 || value === '0') return false;
		return Boolean(value);
	}

	function sanitizeEntry(entry) {
		if (!entry || !entry.slug) return null;
		return {
			id: entry.id || entry.slug,
			slug: entry.slug,
			title: entry.title || 'Untitled plan',
			reference: entry.reference || '',
			thumb: entry.thumb || '',
			url: entry.url || `/plan/${entry.slug}`,
			area: toPositiveNumber(entry.area),
			areaM2: toPositiveNumber(entry.areaM2 || entry['area_m2']),
			bedrooms: entry.bedrooms || '',
			bathrooms: entry.bathrooms || '',
			floors: entry.floors || '',
			parking: entry.parking || '',
			price: toPositiveNumber(entry.price),
			hasFree: asBoolean(entry.hasFree ?? entry.has_free),
			categories: entry.categories || '',
			addedAt: entry.addedAt || entry.added_at || '',
		};
	}

	function normalizeList(list) {
		if (!Array.isArray(list)) return [];
		const seen = new Set();
		const normalized = [];
		list.forEach((entry) => {
			const sanitized = sanitizeEntry(entry);
			if (!sanitized || seen.has(sanitized.slug)) return;
			seen.add(sanitized.slug);
			normalized.push(sanitized);
		});
		return normalized;
	}

	function readState() {
		if (!hasStorage()) return [];
		try {
			const raw = localStorage.getItem(STORAGE_KEY);
			if (!raw) return [];
			const parsed = JSON.parse(raw);
			return normalizeList(parsed);
		} catch (error) {
			return [];
		}
	}

	function persistState() {
		if (!hasStorage()) return;
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(compareState));
		} catch (error) {
			console.warn('Unable to persist compare list', error);
		}
	}

	function setStateFrom(list) {
		compareState = normalizeList(list).slice(0, MAX_ITEMS);
		persistState();
		refreshUI();
	}

	function applyState(mutator) {
		const workingCopy = compareState.slice();
		const next = mutator(workingCopy);
		setStateFrom(Array.isArray(next) ? next : []);
	}

	function planFromDataset(source) {
		const slug = source.getAttribute('data-plan-slug');
		if (!slug) return null;
		const entry = {
			id: source.getAttribute('data-plan-id') || slug,
			slug,
			title: source.getAttribute('data-plan-title') || 'Untitled plan',
			reference: source.getAttribute('data-plan-reference') || '',
			thumb: source.getAttribute('data-plan-thumb') || '',
			url: source.getAttribute('data-plan-url') || `/plan/${slug}`,
			area: source.getAttribute('data-plan-area') || '',
			area_m2: source.getAttribute('data-plan-area-m2') || '',
			bedrooms: source.getAttribute('data-plan-bedrooms') || '',
			bathrooms: source.getAttribute('data-plan-bathrooms') || '',
			floors: source.getAttribute('data-plan-floors') || '',
			parking: source.getAttribute('data-plan-parking') || '',
			price: source.getAttribute('data-plan-price') || '',
			has_free: source.getAttribute('data-plan-free'),
			categories: source.getAttribute('data-plan-categories') || '',
			addedAt: new Date().toISOString(),
		};
		return sanitizeEntry(entry);
	}

	function updateToggleVisual(btn, isActive) {
		btn.classList.toggle('is-active', isActive);
		btn.setAttribute('aria-pressed', String(isActive));
		const label = btn.querySelector('.compare-toggle__label');
		if (label) {
			label.textContent = isActive ? 'In compare' : 'Add to compare';
		}
	}

	function syncCompareButtons(list) {
		const activeSlugs = new Set(list.map((plan) => plan.slug));
		document.querySelectorAll('[data-compare-toggle]').forEach((btn) => {
			const slug = btn.getAttribute('data-plan-slug');
			if (!slug) return;
			updateToggleVisual(btn, activeSlugs.has(slug));
		});
	}

	function syncClearButtons(hasItems) {
		document.querySelectorAll('[data-compare-clear]').forEach((btn) => {
			btn.hidden = !hasItems;
		});
	}

	function renderCompareTray(plans) {
		const tray = document.getElementById('compareTray');
		if (!tray) return;
		if (!plans.length) {
			tray.hidden = true;
			tray.innerHTML = '';
			return;
		}
		tray.hidden = false;
		const frag = document.createDocumentFragment();
		const meta = document.createElement('div');
		meta.className = 'compare-tray__meta';
		meta.innerHTML = `<span>Compare tray</span><span>${plans.length}/${MAX_ITEMS} selected</span>`;
		frag.appendChild(meta);

		const chips = document.createElement('div');
		chips.className = 'compare-tray__plans';
		plans.forEach((plan) => {
			const chip = document.createElement('span');
			chip.className = 'compare-chip';
			const label = document.createElement('strong');
			label.textContent = plan.reference || plan.title;
			chip.appendChild(label);
			if (plan.title && plan.reference) {
				const title = document.createElement('span');
				title.textContent = plan.title;
				chip.appendChild(title);
			}
			const removeBtn = document.createElement('button');
			removeBtn.type = 'button';
			removeBtn.setAttribute('aria-label', `Remove ${plan.title} from compare`);
			removeBtn.setAttribute('data-compare-remove', plan.slug);
			removeBtn.textContent = '×';
			chip.appendChild(removeBtn);
			chips.appendChild(chip);
		});
		frag.appendChild(chips);

		const message = document.createElement('p');
		message.className = 'compare-tray__message';
		message.setAttribute('data-compare-message', 'true');
		message.hidden = true;
		frag.appendChild(message);

		const actions = document.createElement('div');
		actions.className = 'compare-tray__actions';
		actions.innerHTML = `
			<a class="btn btn-primary" href="/compare">Open compare</a>
			<button class="btn btn-soft" type="button" data-compare-clear>Clear all</button>
		`;
		frag.appendChild(actions);

		tray.innerHTML = '';
		tray.appendChild(frag);
	}

	function renderInlineCompare(plans) {
		const bar = document.getElementById('compareInlineBar');
		if (!bar) return;
		const thresholdMet = plans.length >= 2;
		if (!thresholdMet) {
			bar.hidden = true;
			bar.innerHTML = '';
			return;
		}
		bar.hidden = false;
		const summary = plans
			.slice(0, 3)
			.map((plan) => plan.reference || plan.title)
			.filter(Boolean)
			.join(' • ');
		bar.innerHTML = `
			<div class="compare-inline__text">
				<strong>${plans.length} plan${plans.length === 1 ? '' : 's'} ready to compare</strong>
				<p>${summary || 'Select plans to compare specs side by side.'}</p>
			</div>
			<div class="compare-inline__actions">
				<a class="btn btn-primary" href="/compare">Launch compare</a>
				<button class="compare-inline__clear" type="button" data-compare-clear>Clear</button>
			</div>
		`;
	}

	function formatArea(plan) {
		const area = typeof plan.area === 'number' ? Math.round(plan.area) : null;
		const areaM2 = typeof plan.areaM2 === 'number' ? Math.round(plan.areaM2) : null;
		if (area && areaM2) {
			return `${area.toLocaleString()} sq ft / ${areaM2.toLocaleString()} m²`;
		}
		if (area) {
			return `${area.toLocaleString()} sq ft`;
		}
		if (areaM2) {
			return `${areaM2.toLocaleString()} m²`;
		}
		return '—';
	}

	function formatPriceValue(plan) {
		if (typeof plan.price === 'number') {
			return `From $${Math.round(plan.price).toLocaleString()}`;
		}
		return plan.hasFree ? 'Free preview available' : 'On request';
	}

	function buildHeaderRow(plans) {
		const row = document.createElement('div');
		row.className = 'compare-table__head';
		const label = document.createElement('div');
		label.className = 'compare-table__cell compare-table__cell--label';
		label.textContent = 'Plan overview';
		row.appendChild(label);
		plans.forEach((plan) => {
			const cell = document.createElement('div');
			cell.className = 'compare-table__cell';
			const title = document.createElement('h3');
			title.className = 'compare-table__plan-title';
			title.textContent = plan.title;
			cell.appendChild(title);
			const metaParts = [];
			if (plan.reference) metaParts.push(`Ref ${plan.reference}`);
			const areaLabel = formatArea(plan);
			if (areaLabel && areaLabel !== '—') metaParts.push(areaLabel);
			if (plan.bedrooms) metaParts.push(`${plan.bedrooms} beds`);
			if (metaParts.length) {
				const meta = document.createElement('p');
				meta.className = 'compare-table__meta';
				meta.textContent = metaParts.join(' · ');
				cell.appendChild(meta);
			}
			const price = document.createElement('p');
			price.className = 'compare-price-pill';
			price.textContent = formatPriceValue(plan);
			cell.appendChild(price);
			const actions = document.createElement('div');
			actions.className = 'compare-table__meta';
			const link = document.createElement('a');
			link.className = 'btn btn-soft';
			link.href = plan.url;
			link.textContent = 'Open detail';
			actions.appendChild(link);
			const removeBtn = document.createElement('button');
			removeBtn.type = 'button';
			removeBtn.className = 'compare-remove';
			removeBtn.setAttribute('data-compare-remove', plan.slug);
			removeBtn.textContent = 'Remove';
			actions.appendChild(removeBtn);
			cell.appendChild(actions);
			row.appendChild(cell);
		});
		return row;
	}

	function buildRow(rowConfig, plans) {
		const row = document.createElement('div');
		row.className = 'compare-table__row';
		const label = document.createElement('div');
		label.className = 'compare-table__cell compare-table__cell--label';
		label.textContent = rowConfig.label;
		row.appendChild(label);
		plans.forEach((plan) => {
			const cell = document.createElement('div');
			cell.className = 'compare-table__cell';
			const value = rowConfig.formatter(plan);
			cell.textContent = value || '—';
			row.appendChild(cell);
		});
		return row;
	}

	function renderComparePage(plans) {
		const table = document.getElementById('compareTable');
		const wrapper = document.getElementById('compareTableWrapper');
		const emptyState = document.getElementById('compareEmpty');
		const exportBtn = document.querySelector('[data-compare-export]');
		if (!table || !wrapper || !emptyState) {
			if (exportBtn) {
				exportBtn.hidden = plans.length === 0;
			}
			return;
		}
		const hasPlans = plans.length > 0;
		wrapper.hidden = !hasPlans;
		emptyState.hidden = hasPlans;
		table.innerHTML = '';
		if (!hasPlans) {
			if (exportBtn) exportBtn.hidden = true;
			return;
		}
		if (exportBtn) exportBtn.hidden = false;
		table.appendChild(buildHeaderRow(plans));
		SPEC_ROWS.forEach((config) => {
			table.appendChild(buildRow(config, plans));
		});
	}

	function showLimitNotice() {
		const tray = document.getElementById('compareTray');
		if (!tray) {
			window.alert(`Compare up to ${MAX_ITEMS} plans at once.`);
			return;
		}
		tray.classList.add('compare-tray--shake');
		window.setTimeout(() => tray.classList.remove('compare-tray--shake'), 650);
		const message = tray.querySelector('[data-compare-message]');
		if (message) {
			message.textContent = `Compare tray holds ${MAX_ITEMS} plans. Remove one to add another.`;
			message.hidden = false;
			window.clearTimeout(limitNoticeTimer);
			limitNoticeTimer = window.setTimeout(() => {
				const trayEl = document.getElementById('compareTray');
				if (!trayEl) return;
				const msgEl = trayEl.querySelector('[data-compare-message]');
				if (msgEl) {
					msgEl.hidden = true;
				}
			}, 3200);
		}
	}

	function toggleCompare(btn) {
		const slug = btn.getAttribute('data-plan-slug');
		if (!slug) return;
		const existingIndex = compareState.findIndex((plan) => plan.slug === slug);
		if (existingIndex !== -1) {
			applyState((list) => {
				list.splice(existingIndex, 1);
				return list;
			});
			return;
		}
		if (compareState.length >= MAX_ITEMS) {
			showLimitNotice();
			return;
		}
		const plan = planFromDataset(btn);
		if (!plan) return;
		applyState((list) => {
			list.push(plan);
			return list;
		});
	}

	function removePlan(slug) {
		applyState((list) => list.filter((plan) => plan.slug !== slug));
	}

	function clearCompare() {
		setStateFrom([]);
	}

	function handleExport() {
		window.print();
	}

	function refreshUI() {
		const snapshot = compareState.slice();
		syncCompareButtons(snapshot);
		renderCompareTray(snapshot);
		renderInlineCompare(snapshot);
		renderComparePage(snapshot);
		syncClearButtons(snapshot.length > 0);
	}

	function bootstrap() {
		compareState = readState();
		refreshUI();
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', bootstrap);
	} else {
		bootstrap();
	}

	document.addEventListener('compare:refresh', refreshUI);
	window.addEventListener('storage', (event) => {
		if (event.key !== STORAGE_KEY) return;
		compareState = readState();
		refreshUI();
	});

	document.addEventListener('click', (event) => {
		const target = event.target;
		if (!(target instanceof HTMLElement)) return;
		const toggleBtn = target.closest('[data-compare-toggle]');
		if (toggleBtn) {
			event.preventDefault();
			event.stopPropagation();
			toggleCompare(toggleBtn);
			return;
		}
		const removeBtn = target.closest('[data-compare-remove]');
		if (removeBtn) {
			event.preventDefault();
			const slug = removeBtn.getAttribute('data-compare-remove');
			if (slug) {
				removePlan(slug);
			}
			return;
		}
		const clearBtn = target.closest('[data-compare-clear]');
		if (clearBtn) {
			event.preventDefault();
			clearCompare();
			return;
		}
		const exportBtn = target.closest('[data-compare-export]');
		if (exportBtn) {
			event.preventDefault();
			handleExport();
		}
	});
})();

// Newsletter opt-in ------------------------------------------------------
(function () {
	const form = document.querySelector('[data-newsletter-form]');
	if (!form) return;
	const messageEl = document.querySelector('[data-newsletter-message]');
	let isSubmitting = false;

	async function submitNewsletter(event) {
		event.preventDefault();
		if (isSubmitting) return;
		const formData = new FormData(form);
		const email = (formData.get('email') || '').toString().trim();
		if (!email) {
			setMessage('Please enter an email.', true);
			return;
		}
		isSubmitting = true;
		setMessage('Sending...', false);
		try {
			const resp = await fetch('/newsletter', {
				method: 'POST',
				headers: { 'X-Requested-With': 'fetch' },
				body: new URLSearchParams({ email }),
			});
			const data = await resp.json();
			if (!resp.ok || !data.ok) {
				throw new Error(data.message || 'Network error');
			}
			form.reset();
			setMessage(data.message || 'Thanks!', false);
		} catch (error) {
			setMessage(error.message || 'We cannot sign you up right now.', true);
		} finally {
			isSubmitting = false;
		}
	}

	function setMessage(text, isError) {
		if (!messageEl) return;
		messageEl.hidden = false;
		messageEl.textContent = text;
		messageEl.classList.toggle('is-error', Boolean(isError));
	}

	form.addEventListener('submit', submitNewsletter);
})();

// Favorites (localStorage powered) ---------------------------------------
(function () {
	const STORAGE_KEY = 'myfreehouseplan:favorites';

	function hasStorage() {
		try {
			const testKey = '__fav_test__';
			localStorage.setItem(testKey, '1');
			localStorage.removeItem(testKey);
			return true;
		} catch (err) {
			return false;
		}
	}

	function readFavorites() {
		if (!hasStorage()) return {};
		try {
			const raw = localStorage.getItem(STORAGE_KEY);
			if (!raw) return {};
			const parsed = JSON.parse(raw);
			return typeof parsed === 'object' && parsed !== null ? parsed : {};
		} catch (err) {
			return {};
		}
	}

	function writeFavorites(data) {
		if (!hasStorage()) return;
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
		} catch (err) {
			console.warn('Unable to persist favorites', err);
		}
	}

	function favoritesAsArray() {
		const map = readFavorites();
		return Object.values(map).sort((a, b) => {
			return (b.savedAt || '').localeCompare(a.savedAt || '');
		});
	}

	function updateToggleVisual(btn, isActive) {
		btn.classList.toggle('is-active', isActive);
		btn.setAttribute('aria-pressed', String(isActive));
		const label = btn.querySelector('.favorite-toggle__label');
		if (label) {
			label.textContent = isActive ? 'Favorited' : 'Add to favorites';
		}
		const icon = btn.querySelector('.favorite-toggle__icon');
		if (icon) {
			icon.textContent = isActive ? '♥' : '♡';
		}
	}

	function syncFavoriteButtons() {
		const favorites = readFavorites();
		document.querySelectorAll('[data-favorite-toggle]').forEach((btn) => {
			const slug = btn.getAttribute('data-plan-slug');
			if (!slug) return;
			const isActive = Boolean(favorites[slug]);
			updateToggleVisual(btn, isActive);
		});
	}

	function toggleFavorite(btn) {
		const slug = btn.getAttribute('data-plan-slug');
		if (!slug) return;
		const favorites = readFavorites();
		if (favorites[slug]) {
			delete favorites[slug];
		} else {
			favorites[slug] = {
				id: btn.getAttribute('data-plan-id') || slug,
				slug,
				title: btn.getAttribute('data-plan-title') || 'Untitled plan',
				reference: btn.getAttribute('data-plan-reference') || '',
				thumb: btn.getAttribute('data-plan-thumb') || '',
				savedAt: new Date().toISOString(),
			};
		}
		writeFavorites(favorites);
		syncFavoriteButtons();
		renderFavoritesPage();
	}

	function renderFavoritesPage() {
		const grid = document.getElementById('favoritesGrid');
		const empty = document.getElementById('favoritesEmpty');
		const clearBtn = document.querySelector('[data-favorites-clear]');
		if (!grid || !empty) return;

		const favorites = favoritesAsArray();
		grid.innerHTML = '';
		const hasFavorites = favorites.length > 0;
		empty.style.display = hasFavorites ? 'none' : 'block';
		grid.setAttribute('aria-busy', hasFavorites ? 'false' : 'false');
		if (clearBtn) {
			clearBtn.hidden = !hasFavorites;
		}

		if (!hasFavorites) {
			return;
		}

		favorites.forEach((fav) => {
			const article = document.createElement('article');
			article.className = 'favorite-card';
			article.innerHTML = `
				<div class="favorite-card__media">
					${fav.thumb ? `<img src="${fav.thumb}" alt="${fav.title}">` : '<div class="plan-card__placeholder">Preview coming soon</div>'}
				</div>
				<div class="favorite-card__body">
					<h3>${fav.title}</h3>
					<p class="favorite-card__meta">
						<span>Ref ${fav.reference || '—'}</span>
					</p>
				</div>
				<div class="favorite-card__actions">
					<a class="btn btn-primary" href="/plan/${fav.slug}">View plan</a>
					<button type="button" class="favorite-card__remove" data-favorite-remove="${fav.slug}">Remove</button>
				</div>
			`;
			grid.appendChild(article);
		});
	}

	function clearFavorites() {
		writeFavorites({});
		syncFavoriteButtons();
		renderFavoritesPage();
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', () => {
			syncFavoriteButtons();
			renderFavoritesPage();
		});
	} else {
		syncFavoriteButtons();
		renderFavoritesPage();
	}

	window.addEventListener('storage', (event) => {
		if (event.key !== STORAGE_KEY) return;
		syncFavoriteButtons();
		renderFavoritesPage();
	});

	document.addEventListener('favorites:refresh', () => {
		syncFavoriteButtons();
	});

	document.addEventListener('click', (event) => {
		const target = event.target;
		if (!(target instanceof HTMLElement)) return;
		const toggleBtn = target.closest('[data-favorite-toggle]');
		if (toggleBtn) {
			event.preventDefault();
			event.stopPropagation();
			toggleFavorite(toggleBtn);
			return;
		}
		const removeBtn = target.closest('[data-favorite-remove]');
		if (removeBtn) {
			const slug = removeBtn.getAttribute('data-favorite-remove');
			if (!slug) return;
			const favorites = readFavorites();
			delete favorites[slug];
			writeFavorites(favorites);
			syncFavoriteButtons();
			renderFavoritesPage();
		}
	});

	const clearBtn = document.querySelector('[data-favorites-clear]');
	if (clearBtn) {
		clearBtn.addEventListener('click', (event) => {
			event.preventDefault();
			clearFavorites();
		});
	}
})();
