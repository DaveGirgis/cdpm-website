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
    cancellations = cancellations
      .filter((c) => c && c.date)
      .map((c) => ({ date: String(c.date).slice(0, 10), event: c.event || "match", note: c.note || "" }));
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const fmt = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    const fmtShort = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric" });
    const cancelled = (event, d) => cancellations.find((c) => c.event === event && c.date === iso(d));

    // Every cancellation still ahead, in red at the top of the box, so people
    // see it as soon as it's posted (it drops off by itself once the day passes).
    const list = box.querySelector("[data-alerts]");
    const ahead = cancellations.filter((c) => c.date >= iso(today)).sort((a, b) => a.date.localeCompare(b.date));
    if (list && ahead.length) {
      for (const c of ahead) {
        const [y, m, dd] = c.date.split("-").map(Number);
        const li = document.createElement("li");
        const strong = document.createElement("strong");
        strong.textContent = `${c.event === "workshop" ? "Workshop" : "Match"}, ${fmtShort.format(new Date(y, m - 1, dd))}:`;
        li.append(strong, ` ${c.note || "Cancelled"}`);
        list.append(li);
      }
      list.hidden = false;
    }

    for (const [event, n] of Object.entries(EVENTS)) {
      const dateEl = box.querySelector(`[data-next="${event}"]`);
      const noteEl = box.querySelector(`[data-note="${event}"]`);
      if (!dateEl) continue;
      const d = next(n, today);
      dateEl.textContent = fmt.format(d);
      if (cancelled(event, d) && noteEl) {
        // Cross out the cancelled date and give the next one that's on.
        let after = d;
        do { after = next(n, new Date(after.getFullYear(), after.getMonth(), after.getDate() + 1)); }
        while (cancelled(event, after));
        dateEl.classList.add("cancelled");
        noteEl.textContent = `Cancelled. Next ${event}: ${fmt.format(after)}`;
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
