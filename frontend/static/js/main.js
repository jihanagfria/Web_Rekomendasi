async function fetchProductData() {
  const response = await fetch('/api/products', { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`Gagal memuat produk (HTTP ${response.status}).`);
  const productData = await response.json();
  if (!Array.isArray(productData)) throw new TypeError('Format data produk harus berupa array JSON.');
  return productData;
}

async function fetchRecommendations(preferences) {
  const response = await fetch('/api/recommendations', {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(preferences)
  });
  const responseData = await response.json();
  if (!response.ok) throw new Error(responseData.error || `Gagal menghitung rekomendasi (HTTP ${response.status}).`);
  if (!Array.isArray(responseData)) throw new TypeError('Format hasil rekomendasi harus berupa array JSON.');
  return responseData;
}


function showView(target) {
  document.querySelectorAll('.app-view').forEach(view => {
    view.classList.toggle('is-hidden', view.dataset.view !== target);
  });
  document.querySelectorAll('[data-view-target]').forEach(control => {
    control.classList.toggle('active', control.dataset.viewTarget === target && control.classList.contains('nav-link'));
  });
  window.scrollTo({ top: 0, behavior: 'auto' });
}

function initViewNavigation() {
  document.querySelectorAll('[data-view-target]').forEach(control => {
    control.addEventListener('click', () => showView(control.dataset.viewTarget));
  });
}
let products = [];
let activeCatalogFilter = '';
const byId = id => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
}

function imageUrl(filename) {
  return `/static/images/${encodeURIComponent(filename || 'placeholder.jpg')}`;
}

function attachImageFallbacks(container) {
  container.querySelectorAll('img').forEach(image => {
    image.addEventListener('error', () => { image.src = imageUrl('placeholder.jpg'); }, { once: true });
  });
}

function tagsFor(product) {
  return {
    skinTypes: String(product.skinType ?? '').split(',').map(value => value.trim()).filter(Boolean),
    finishes: String(product.finish ?? '').split(',').map(value => value.trim()).filter(Boolean),
    benefits: String(product.benefits ?? '').split(',').map(value => value.trim()).filter(Boolean)
  };
}

function normalizedBenefitsFor(product) {
  return String(product.cbfBenefits ?? '').split(',').map(value => value.trim()).filter(Boolean);
}

function renderProductCard(product) {
  const { skinTypes, finishes, benefits } = tagsFor(product);
  return `
    <article class="product-card" data-subcategory="${escapeHtml(product.subCategory)}">
      <div class="product-img-placeholder">
        <img src="${imageUrl(product.image)}" alt="${escapeHtml(product.name)}" loading="lazy">
      </div>
      <div class="product-body">
        <div class="product-category">${escapeHtml(product.subCategory)} &middot; ${escapeHtml(product.brand)}</div>
        <div class="product-name">${escapeHtml(product.name)}</div>
        <div class="product-tags product-profile-tags">
          ${skinTypes.map(tag => `<span class="tag skin-tag">${escapeHtml(tag)}</span>`).join('')}
          ${finishes.map(tag => `<span class="tag finish-tag">${escapeHtml(tag)}</span>`).join('')}
        </div>
        <div class="product-tags product-benefit-tags">
          ${benefits.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
        </div>
      </div>
    </article>`;
}

function renderCatalog() {
  const grid = byId('catalogGrid');
  const searchTerm = byId('catalogSearch').value.trim().toLowerCase();
  if (activeCatalogFilter === null && searchTerm === '') {
    grid.innerHTML = '<div class="empty-state"><h3>Pilih subkategori atau cari produk</h3><p>Produk akan ditampilkan setelah Anda memilih subkategori atau mengetik pencarian.</p></div>';
    return;
  }

  let visibleProducts = activeCatalogFilter
    ? products.filter(product => product.subCategory === activeCatalogFilter)
    : products;

  if (searchTerm) {
    visibleProducts = visibleProducts.filter(product => [
      product.name, product.brand, product.subCategory, product.skinType, product.finish, product.benefits
    ].some(value => String(value ?? '').toLowerCase().includes(searchTerm)));
  }

  if (!visibleProducts.length) {
    grid.innerHTML = '<div class="empty-state"><h3>Produk tidak ditemukan</h3><p>Coba kata kunci atau subkategori yang berbeda.</p></div>';
    return;
  }
  grid.innerHTML = visibleProducts.map(renderProductCard).join('');
  attachImageFallbacks(grid);
}

function initChips(groupId) {
  const group = byId(groupId);
  group.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const allChip = group.querySelector('.chip[data-value=""]');
      if (chip === allChip) {
        const activateAll = !allChip.classList.contains('active');
        group.querySelectorAll('.chip').forEach(item => item.classList.remove('active'));
        allChip.classList.toggle('active', activateAll);
        return;
      }
      allChip?.classList.remove('active');
      chip.classList.toggle('active');
    });
  });
}

function selectedChips(groupId) {
  const group = byId(groupId);
  const allChip = group.querySelector('.chip[data-value=""]');

  if (groupId === 'chips-subcategory' && allChip?.classList.contains('active')) {
    return [...group.querySelectorAll('.chip[data-value]:not([data-value=""])')]
      .map(chip => chip.dataset.value);
  }

  return [...group.querySelectorAll('.chip.active[data-value]:not([data-value=""])')]
    .map(chip => chip.dataset.value);
}

function currentPreferences() {
  return {
    subCategories: selectedChips('chips-subcategory'),
    skinTypes: selectedChips('chips-skin'),
    finishes: selectedChips('chips-finish'),
    benefits: selectedChips('chips-benefit')
  };
}

function optionsFromProduct(product, productField) {
  return String(product[productField] ?? '').split(',').map(value => value.trim()).filter(Boolean);
}

const SUBCATEGORY_ORDER = [
  'Cushion',
  'Foundation',
  'Skin Tint',
  'Powder'
];

function populateProductChips(groupId, productField) {
  const group = byId(groupId);
  const optionStats = new Map();
  products.forEach(product => {
    const uniqueOptions = new Map();
    optionsFromProduct(product, productField).forEach(option => uniqueOptions.set(option.toLowerCase(), option));
    uniqueOptions.forEach((label, key) => {
      const current = optionStats.get(key) ?? { label, count: 0 };
      current.count += 1;
      optionStats.set(key, current);
    });
  });

  const sortedOptions = [...optionStats.values()].sort((a, b) => {
  if (groupId === 'chips-subcategory') {
    return (
      SUBCATEGORY_ORDER.indexOf(a.label) -
      SUBCATEGORY_ORDER.indexOf(b.label)
    );
  }

  return b.count - a.count || a.label.localeCompare(b.label, 'id');
});

group.insertAdjacentHTML('beforeend', sortedOptions
    .map(option => `<button class="chip" data-value="${escapeHtml(option.label)}">${escapeHtml(option.label)}</button>`)
    .join(''));
}

function renderResultCard(product, index) {
  const isBestMatch = index === 0;
  const { skinTypes, finishes } = tagsFor(product);
  const benefits = normalizedBenefitsFor(product);
  return `
    <article class="result-card ${isBestMatch ? 'top-match' : ''}">
      ${isBestMatch ? '<div class="best-match-badge">Best Match</div>' : ''}
      <div class="result-img-wrap"><img src="${imageUrl(product.image)}" alt="${escapeHtml(product.name)}" loading="lazy"></div>
      <div class="result-body">
        <div class="result-category">${escapeHtml(product.subCategory)} &middot; ${escapeHtml(product.brand)}</div>
        <div class="result-name">${escapeHtml(product.name)}</div>
        <div class="result-tags result-profile-tags">
          ${skinTypes.map(tag => `<span class="tag skin-tag">${escapeHtml(tag)}</span>`).join('')}
          ${finishes.map(tag => `<span class="tag finish-tag">${escapeHtml(tag)}</span>`).join('')}
        </div>
        <div class="result-tags result-benefit-tags">
          ${benefits.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
        </div>
      </div>
    </article>`;
}

function showResults(recommendations) {
  const section = byId('resultsSection');
  const grid = byId('resultsGrid');
  const subtitle = byId('resultsSubtitle');
  if (!recommendations.length) {
    subtitle.textContent = '';
    grid.innerHTML = '<div class="empty-state"><h3>Belum ada produk yang sesuai</h3><p>Silakan ubah subkategori atau preferensi lainnya.</p></div>';
  } else {
    subtitle.textContent = `${recommendations.length} produk yang paling sesuai dengan preferensi Anda`;
    grid.innerHTML = recommendations.map(renderResultCard).join('');
    attachImageFallbacks(grid);
  }
  section.classList.remove('is-hidden');
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function initCatalogFilters() {
  document.querySelectorAll('.filter-btn').forEach(button => {
    button.addEventListener('click', () => {
      const isCurrentlyActive = button.classList.contains('active');
      document.querySelectorAll('.filter-btn').forEach(item => item.classList.remove('active'));
      if (isCurrentlyActive) activeCatalogFilter = null;
      else { button.classList.add('active'); activeCatalogFilter = button.dataset.filter; }
      renderCatalog();
    });
  });
}

function initCatalogSearch() {
  const searchInput = byId('catalogSearch');
  const clearButton = byId('clearCatalogSearch');
  searchInput.addEventListener('input', () => {
    clearButton.classList.toggle('is-hidden', searchInput.value.length === 0);
    renderCatalog();
  });
  clearButton.addEventListener('click', () => {
    searchInput.value = '';
    clearButton.classList.add('is-hidden');
    searchInput.focus();
    renderCatalog();
  });
}

function resetPreferences() {
  byId('resultsSection').classList.add('is-hidden');
  ['chips-subcategory', 'chips-skin', 'chips-finish', 'chips-benefit'].forEach(groupId => {
    byId(groupId).querySelectorAll('.chip').forEach((chip, index) => {
      const shouldActivate = index === 0;
      chip.classList.toggle('active', shouldActivate);
    });
  });
  byId('preferences').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function initializeApp() {
  const catalogGrid = byId('catalogGrid');
  catalogGrid.innerHTML = '<p class="loading-msg">Memuat produk...</p>';
  try { products = await fetchProductData(); }
  catch (error) {
    catalogGrid.innerHTML = `<p class="loading-msg">Gagal memuat produk: ${escapeHtml(error.message)}</p>`;
    console.error(error);
    return;
  }

  renderCatalog();
  initViewNavigation();
  initCatalogFilters();
  initCatalogSearch();
  populateProductChips('chips-subcategory', 'subCategory');
  populateProductChips('chips-finish', 'finish');
  ['chips-subcategory', 'chips-skin', 'chips-finish', 'chips-benefit'].forEach(initChips);

  const recommendButton = byId('btnRecommend');
  recommendButton.addEventListener('click', async () => {
    const preferences = currentPreferences();
    if (!preferences.subCategories.length) {
      showResults([]);
      byId('resultsSubtitle').textContent = 'Pilih minimal satu subkategori produk untuk mendapatkan rekomendasi.';
      return;
    }
    if (![preferences.skinTypes, preferences.finishes, preferences.benefits].some(values => values.length)) {
      showResults([]);
      byId('resultsSubtitle').textContent = 'Pilih minimal satu jenis kulit, hasil akhir/efek, atau kebutuhan makeup.';
      return;
    }

    recommendButton.disabled = true;
    try { showResults(await fetchRecommendations(preferences)); }
    catch (error) { showResults([]); byId('resultsSubtitle').textContent = error.message; console.error(error); }
    finally { recommendButton.disabled = false; }
  });
  byId('btnReset').addEventListener('click', resetPreferences);
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initializeApp, { once: true });
else initializeApp();






