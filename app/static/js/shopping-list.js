// Persist shopping-list ticks in localStorage so a shopping trip survives reloads.
(function () {
  "use strict";

  const list = document.getElementById("shopping-list");
  if (!list) return;

  const storageKey = "recipebook-shopping:" + (list.dataset.range || "default");
  const counter = document.getElementById("shopping-count");
  const tickedLabel = list.dataset.ticked || "ticked";
  let checked = new Set();

  try {
    checked = new Set(JSON.parse(localStorage.getItem(storageKey) || "[]"));
  } catch (error) {
    checked = new Set();
  }

  function apply() {
    list.querySelectorAll("[data-shopping-item]").forEach((box) => {
      const item = box.closest("li");
      const isChecked = checked.has(item.dataset.key);
      box.checked = isChecked;
      item.classList.toggle("done", isChecked);
    });
    if (counter) {
      counter.textContent = checked.size ? "· " + checked.size + " " + tickedLabel : "";
    }
  }

  function save() {
    try {
      localStorage.setItem(storageKey, JSON.stringify([...checked]));
    } catch (error) {
      /* storage unavailable / full - ticks just won't persist */
    }
  }

  list.addEventListener("change", (event) => {
    const box = event.target;
    if (!box.matches("[data-shopping-item]")) return;
    const key = box.closest("li").dataset.key;
    if (box.checked) checked.add(key);
    else checked.delete(key);
    save();
    apply();
  });

  const reset = document.getElementById("shopping-reset");
  if (reset) {
    reset.addEventListener("click", () => {
      checked.clear();
      try {
        localStorage.removeItem(storageKey);
      } catch (error) {
        /* ignore */
      }
      apply();
    });
  }

  apply();
})();
