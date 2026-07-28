"use strict";

const form = document.getElementById("login-form");
const errorEl = document.getElementById("login-error");
const btn = document.getElementById("login-btn");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.hidden = true;
  btn.disabled = true;
  btn.textContent = "Connexion…";
  try {
    const r = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: document.getElementById("username").value,
        password: document.getElementById("password").value,
      }),
    });
    const data = await r.json();
    if (data.ok) {
      window.location.href = "/";
      return;
    }
    errorEl.textContent = data.error || "Connexion refusée.";
    errorEl.hidden = false;
  } catch (e) {
    errorEl.textContent = "Serveur injoignable.";
    errorEl.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Se connecter";
  }
});
