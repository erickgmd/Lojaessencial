document.addEventListener("DOMContentLoaded", () => {
  const grid = document.getElementById("productGrid");
  const cards = [...grid.querySelectorAll(".product-card")];
  const inputs = {
    search: document.getElementById("searchInput"),
    category: document.getElementById("categoryFilter"),
    brand: document.getElementById("brandFilter"),
    min: document.getElementById("minPrice"),
    max: document.getElementById("maxPrice"),
    size: document.getElementById("sizeFilter"),
    color: document.getElementById("colorFilter"),
    promo: document.getElementById("promoFilter"),
    launch: document.getElementById("launchFilter")
  };

  const params = new URLSearchParams(window.location.search);
  if (params.get("category")) inputs.category.value = params.get("category");
  if (params.get("brand")) inputs.brand.value = params.get("brand");
  if (params.get("q")) inputs.search.value = params.get("q");
  if (params.get("promo") === "1") inputs.promo.checked = true;
  if (params.get("launch") === "1") inputs.launch.checked = true;

  function applyFilters() {
    const query = inputs.search.value.toLowerCase().trim();
    let visible = cards.filter(card => {
      const searchable = `${card.dataset.name} ${card.dataset.code} ${card.dataset.category} ${card.dataset.brand}`.toLowerCase();
      const price = Number(card.dataset.price);
      const hasDiscount = !!card.querySelector(".line-through");
      return (!query || searchable.includes(query))
        && (!inputs.category.value || card.dataset.category === inputs.category.value)
        && (!inputs.brand.value || card.dataset.brand === inputs.brand.value)
        && (!inputs.min.value || price >= Number(inputs.min.value))
        && (!inputs.max.value || price <= Number(inputs.max.value))
        && (!inputs.size.value || card.dataset.sizes.includes(inputs.size.value.toLowerCase()))
        && (!inputs.color.value || card.dataset.colors.includes(inputs.color.value.toLowerCase()))
        && (!inputs.promo.checked || hasDiscount)
        && (!inputs.launch.checked || card.dataset.launch === "true");
    });

    cards.forEach(card => card.classList.toggle("hidden", !visible.includes(card)));
    document.getElementById("resultCount").textContent = `${visible.length} produto${visible.length === 1 ? "" : "s"}`;
    document.getElementById("emptyState").classList.toggle("hidden", visible.length !== 0);
  }

  Object.values(inputs).forEach(input => input.addEventListener("input", applyFilters));
  applyFilters();
  document.getElementById("clearFilters").addEventListener("click", () => {
    Object.values(inputs).forEach(input => input.type === "checkbox" ? input.checked = false : input.value = "");
    applyFilters();
  });

  document.getElementById("sortFilter").addEventListener("change", event => {
    const mode = event.target.value;
    const sorted = [...cards].sort((a,b) => {
      if (mode === "price-asc") return Number(a.dataset.price) - Number(b.dataset.price);
      if (mode === "price-desc") return Number(b.dataset.price) - Number(a.dataset.price);
      if (mode === "name") return a.dataset.name.localeCompare(b.dataset.name);
      return 0;
    });
    sorted.forEach(card => grid.appendChild(card));
  });
});
