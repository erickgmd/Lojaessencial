document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();

  const menuButton = document.getElementById("mobileMenuButton");
  const mobileMenu = document.getElementById("mobileMenu");
  menuButton?.addEventListener("click", () => {
    const opening = mobileMenu.classList.contains("hidden");
    mobileMenu.classList.toggle("hidden");
    menuButton.setAttribute("aria-expanded", String(opening));
  });

  mobileMenu?.querySelectorAll("a").forEach(link => {
    link.addEventListener("click", () => mobileMenu.classList.add("hidden"));
  });

  const mobileFiltersButton = document.getElementById("mobileFiltersButton");
  const filtersPanel = document.getElementById("filtersPanel");
  mobileFiltersButton?.addEventListener("click", () => {
    filtersPanel.classList.toggle("hidden");
    const hidden = filtersPanel.classList.contains("hidden");
    mobileFiltersButton.innerHTML = hidden
      ? `<i data-lucide="sliders-horizontal" class="h-4 w-4"></i> Mostrar filtros`
      : `<i data-lucide="x" class="h-4 w-4"></i> Fechar filtros`;
    lucide.createIcons();
  });

  document.querySelectorAll(".option-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      btn.parentElement.querySelectorAll(".option-btn").forEach(item => item.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  const getFavorites = () => JSON.parse(localStorage.getItem("favorites") || "[]");
  const setFavorites = items => localStorage.setItem("favorites", JSON.stringify(items));

  function refreshFavoriteButtons() {
    const favorites = getFavorites();
    document.querySelectorAll(".favorite-btn").forEach(btn => {
      const active = favorites.includes(btn.dataset.id);
      btn.classList.toggle("text-red-600", active);
      btn.querySelector("svg")?.classList.toggle("fill-current", active);
    });
  }

  document.querySelectorAll(".favorite-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const favorites = getFavorites();
      const id = btn.dataset.id;
      const next = favorites.includes(id) ? favorites.filter(item => item !== id) : [...favorites, id];
      setFavorites(next);
      refreshFavoriteButtons();
    });
  });
  refreshFavoriteButtons();

  document.getElementById("shareButton")?.addEventListener("click", async () => {
    try {
      if (navigator.share) await navigator.share({ title: document.title, url: location.href });
      else {
        await navigator.clipboard.writeText(location.href);
        alert("Link copiado!");
      }
    } catch (_) {}
  });
});
