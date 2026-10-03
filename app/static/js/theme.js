// Light/dark theme toggle.
//
// The initial theme is applied by a tiny inline script in <head> (to avoid a flash of
// the wrong colours); this file wires up the toggle button and follows the OS preference
// while the user has not made an explicit choice.
(function () {
  "use strict";

  var STORAGE_KEY = "recipebook-theme";
  var root = document.documentElement;
  var button = document.getElementById("theme-toggle");
  var media = window.matchMedia("(prefers-color-scheme: dark)");

  function storedTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function currentTheme() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    if (button) {
      button.textContent = theme === "dark" ? "☀️" : "🌙";
      button.setAttribute(
        "aria-label",
        theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
      );
    }
  }

  apply(currentTheme());

  if (button) {
    button.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch (error) {
        /* storage unavailable - choice just won't persist */
      }
      apply(next);
    });
  }

  // Follow the OS while the user has not chosen a theme explicitly.
  if (media.addEventListener) {
    media.addEventListener("change", function (event) {
      if (!storedTheme()) apply(event.matches ? "dark" : "light");
    });
  }
})();
