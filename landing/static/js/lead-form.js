(function () {
  "use strict";

  function utmFromLocation() {
    var out = {};
    try {
      var q = new URLSearchParams(window.location.search);
      ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"].forEach(function (k) {
        var v = (q.get(k) || "").trim();
        if (v) out[k] = v.slice(0, 120);
      });
    } catch (e) { /* ignore */ }
    return out;
  }

  function bindForm(form) {
    var status = form.querySelector(".lead-status");
    var submitBtn = form.querySelector('button[type="submit"]');
    var botLink = form.querySelector(".lead-bot-link");

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (!form.reportValidity()) return;

      var fd = new FormData(form);
      if ((fd.get("company") || "").toString().trim()) {
        if (status) {
          status.hidden = false;
          status.textContent = "Заявка принята. Можно написать в бота.";
          status.className = "lead-status is-ok";
        }
        form.reset();
        return;
      }
      if (!fd.get("consent_pd") || !fd.get("consent_tb") || !fd.get("consent_oferta")) {
        if (status) {
          status.hidden = false;
          status.textContent = "Нужны три отдельные отметки: обработка данных, трансграничная передача и оферта.";
          status.className = "lead-status is-err";
        }
        return;
      }

      var payload = Object.assign(
        {
          name: (fd.get("name") || "").toString().trim(),
          contact: (fd.get("contact") || "").toString().trim(),
          topic: (fd.get("topic") || "").toString().trim(),
          consent: true,
          consent_pd: true,
          consent_tb: true,
          consent_oferta: true,
          source: (fd.get("source") || "site").toString().trim(),
          page: (fd.get("page") || window.location.href).toString().trim(),
        },
        utmFromLocation()
      );

      if (submitBtn) submitBtn.disabled = true;
      if (status) {
        status.hidden = false;
        status.textContent = "Отправляем…";
        status.className = "lead-status";
      }

      fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (r) {
          return r.json().then(function (data) {
            return { ok: r.ok, status: r.status, data: data };
          });
        })
        .then(function (res) {
          if (!res.ok || !res.data || !res.data.ok) {
            throw new Error((res.data && res.data.error) || "Не удалось отправить");
          }
          if (status) {
            status.textContent = "Заявка принята. Можете сразу написать в бота — так быстрее.";
            status.className = "lead-status is-ok";
          }
          if (botLink && res.data.bot_url) botLink.href = res.data.bot_url;
          form.reset();
          var pageInput = form.querySelector('input[name="page"]');
          var sourceInput = form.querySelector('input[name="source"]');
          if (pageInput) pageInput.value = payload.page;
          if (sourceInput) sourceInput.value = payload.source;
        })
        .catch(function (err) {
          if (status) {
            status.textContent = (err && err.message) || "Ошибка отправки. Напишите в Telegram.";
            status.className = "lead-status is-err";
          }
        })
        .finally(function () {
          if (submitBtn) submitBtn.disabled = false;
        });
    });
  }

  document.querySelectorAll("form.lead-form").forEach(bindForm);
})();
