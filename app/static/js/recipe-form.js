// Quick-add tag chips for the recipe form.
//
// The free-text `tags` input stays the single source of truth (so the form works
// without JavaScript); clicking a chip simply appends its tag to that input.
(function () {
  "use strict";

  const input = document.getElementById("tags-input");
  if (!input) return;

  const quick = document.querySelector("[data-quick-tags]");

  function currentTags() {
    return input.value
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
  }

  function hasTag(name) {
    return currentTags().some((tag) => tag.toLowerCase() === name.toLowerCase());
  }

  function addTag(name) {
    const tags = currentTags();
    if (!tags.some((tag) => tag.toLowerCase() === name.toLowerCase())) {
      tags.push(name);
      input.value = tags.join(", ");
    }
    refresh();
  }

  function refresh() {
    if (!quick) return;
    quick.querySelectorAll("[data-quick-tag]").forEach((button) => {
      button.classList.toggle("chip--active", hasTag(button.dataset.quickTag));
    });
  }

  if (quick) {
    quick.addEventListener("click", (event) => {
      const button = event.target.closest("[data-quick-tag]");
      if (button) addTag(button.dataset.quickTag);
    });
  }

  input.addEventListener("input", refresh);
  refresh();
})();
