(function () {
  var STAGES = [
    { id: "new", title: "Новые" },
    { id: "talk", title: "Переписка" },
    { id: "paid", title: "Оплатила" },
    { id: "done", title: "Готово" },
  ];
  var FORMATS = [
    { id: "q1111", title: "1 вопрос · 1111" },
    { id: "v5555", title: "Видео 45 мин · 5555" },
    { id: "full11111", title: "Полный разбор · 11111" },
    { id: "tt3333", title: "TikTok · 3333" },
    { id: "bot", title: "Бот" },
    { id: "other", title: "Другое" },
  ];
  var board = document.getElementById("crm-board");
  var deals = [];

  function fmtLabel(id) {
    var f = FORMATS.find(function (x) {
      return x.id === id;
    });
    return f ? f.title : id;
  }

  function load(importLeads) {
    var q = importLeads ? "?import_leads=1" : "";
    return fetch("/api/crm/deals" + q, { credentials: "same-origin" }).then(function (r) {
      if (r.status === 401) {
        window.location = "/crm/login";
        return null;
      }
      return r.json();
    }).then(function (data) {
      if (!data) return;
      deals = data.deals || [];
      render();
    });
  }

  function save(id, patch) {
    var url = id ? "/api/crm/deals/" + id : "/api/crm/deals";
    var method = id ? "PATCH" : "POST";
    return fetch(url, {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then(function (r) {
      return r.json();
    }).then(function () {
      return load();
    });
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () {
        fn.apply(null, args);
      }, ms);
    };
  }

  function render() {
    if (!board) return;
    board.innerHTML = "";
    STAGES.forEach(function (st) {
      var col = document.createElement("section");
      col.className = "crm-col";
      var list = deals.filter(function (d) {
        return d.stage === st.id;
      });
      var h = document.createElement("h2");
      h.innerHTML = st.title + '<span class="crm-col-count">' + list.length + "</span>";
      col.appendChild(h);
      list.forEach(function (d) {
        col.appendChild(cardEl(d));
      });
      board.appendChild(col);
    });
  }

  function cardEl(d) {
    var el = document.createElement("article");
    el.className = "crm-card";
    el.innerHTML =
      '<input data-k="name" placeholder="Имя" value="">' +
      '<input data-k="contact" placeholder="@username / телефон" value="">' +
      '<div class="crm-card-row">' +
      '<select data-k="format"></select>' +
      '<input data-k="amount" type="number" min="0" placeholder="₽" value="">' +
      "</div>" +
      '<select data-k="stage"></select>' +
      '<textarea data-k="note" placeholder="Заметка"></textarea>' +
      '<button type="button" class="crm-card-del">Удалить</button>';
    el.querySelector('[data-k="name"]').value = d.name || "";
    el.querySelector('[data-k="contact"]').value = d.contact || "";
    el.querySelector('[data-k="amount"]').value = d.amount || "";
    el.querySelector('[data-k="note"]').value = d.note || "";
    var fs = el.querySelector('[data-k="format"]');
    var ss = el.querySelector('[data-k="stage"]');
    FORMATS.forEach(function (f) {
      var o = document.createElement("option");
      o.value = f.id;
      o.textContent = f.title;
      if (f.id === d.format) o.selected = true;
      fs.appendChild(o);
    });
    STAGES.forEach(function (s) {
      var o = document.createElement("option");
      o.value = s.id;
      o.textContent = s.title;
      if (s.id === d.stage) o.selected = true;
      ss.appendChild(o);
    });
    var persist = debounce(function () {
      save(d.id, {
        name: el.querySelector('[data-k="name"]').value,
        contact: el.querySelector('[data-k="contact"]').value,
        format: fs.value,
        stage: ss.value,
        amount: el.querySelector('[data-k="amount"]').value,
        note: el.querySelector('[data-k="note"]').value,
      });
    }, 400);
    el.querySelectorAll("input, select, textarea").forEach(function (node) {
      node.addEventListener("change", persist);
      node.addEventListener("input", persist);
    });
    el.querySelector(".crm-card-del").addEventListener("click", function () {
      if (!window.confirm("Удалить карточку?")) return;
      fetch("/api/crm/deals/" + d.id, { method: "DELETE", credentials: "same-origin" }).then(function () {
        return load();
      });
    });
    return el;
  }

  var addBtn = document.getElementById("crm-add");
  if (addBtn) {
    addBtn.addEventListener("click", function () {
      save(null, { name: "", contact: "", stage: "new", format: "other", source: "manual" });
    });
  }
  var imp = document.getElementById("crm-import");
  if (imp) {
    imp.addEventListener("click", function () {
      load(true);
    });
  }
  load();
})();
