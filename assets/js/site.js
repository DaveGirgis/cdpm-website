// Next match / workshop dates and contact email links.
(function () {
  // Matches run on the first Saturday, workshops on the fourth.
  const EVENTS = { match: 1, workshop: 4 };

  function nthSaturday(year, month, n) {
    const first = new Date(year, month, 1);
    const offset = (6 - first.getDay() + 7) % 7;
    return new Date(year, month, 1 + offset + 7 * (n - 1));
  }

  function iso(d) {
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  function next(n, today) {
    let y = today.getFullYear();
    let m = today.getMonth();
    for (;;) {
      const d = nthSaturday(y, m, n);
      if (d >= today) return d;
      m += 1;
      if (m > 11) { m = 0; y += 1; }
    }
  }

  const box = document.getElementById("next-match");
  if (box) {
    let cancellations = [];
    try { cancellations = JSON.parse(box.dataset.cancellations || "[]") || []; } catch (e) {}
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const fmt = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });

    for (const [event, n] of Object.entries(EVENTS)) {
      const dateEl = box.querySelector(`[data-next="${event}"]`);
      const noteEl = box.querySelector(`[data-note="${event}"]`);
      if (!dateEl) continue;
      const d = next(n, today);
      const off = cancellations.find((c) => c && c.date === iso(d) && (c.event || "match") === event);
      dateEl.textContent = fmt.format(d);
      if (off && noteEl) {
        dateEl.style.textDecoration = "line-through";
        noteEl.textContent = off.note || "Cancelled";
        noteEl.hidden = false;
      }
    }
  }

  for (const a of document.querySelectorAll("a.email[data-u]")) {
    const addr = `${a.dataset.u}@${a.dataset.d}`;
    a.href = `mailto:${addr}`;
    a.title = addr;
  }
})();
