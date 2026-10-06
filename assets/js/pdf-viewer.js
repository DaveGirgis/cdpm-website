// Shows stage-design PDFs inline with PDF.js (self-hosted in /vendor/pdfjs/).
// The library loads only when a viewer scrolls near the screen, and each page
// is drawn only when it's about to be seen.
const viewers = document.querySelectorAll(".pdf-view[data-pdf]");

if (viewers.length) {
  const near = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      near.unobserve(e.target);
      load(e.target);
    }
  }, { rootMargin: "600px 0px" });
  viewers.forEach((v) => near.observe(v));
}

let lib;
async function pdfjs(base) {
  if (!lib) {
    lib = import(`${base}pdf.min.mjs`).then((m) => {
      m.GlobalWorkerOptions.workerSrc = `${base}pdf.worker.min.mjs`;
      return m;
    });
  }
  return lib;
}

async function load(view) {
  const base = view.dataset.pdfjs;
  const status = view.querySelector(".pdf-status");
  const pages = view.querySelector(".pdf-pages");
  try {
    const { getDocument } = await pdfjs(base);
    const doc = await getDocument({
      url: view.dataset.pdf,
      standardFontDataUrl: `${base}standard_fonts/`,
      wasmUrl: `${base}wasm/`,
      enableScripting: false,
    }).promise;

    // A placeholder per page, sized to the page shape so the layout doesn't jump.
    const slots = [];
    for (let n = 1; n <= doc.numPages; n++) {
      const page = await doc.getPage(n);
      const vp = page.getViewport({ scale: 1 });
      const slot = document.createElement("div");
      slot.className = "pdf-page";
      slot.style.aspectRatio = `${vp.width} / ${vp.height}`;
      slot.setAttribute("role", "img");
      slot.setAttribute("aria-label", `Stage designs, page ${n} of ${doc.numPages}`);
      pages.append(slot);
      slots.push([slot, page]);
    }
    status.hidden = true;

    const draw = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        draw.unobserve(e.target);
        const [slot, page] = slots.find(([s]) => s === e.target);
        render(slot, page);
      }
    }, { rootMargin: "400px 0px" });
    slots.forEach(([slot]) => draw.observe(slot));
  } catch (err) {
    console.error(err);
    status.textContent = "The stage designs couldn't be shown here. Use the Download PDF button instead.";
    status.classList.add("pdf-error");
  }
}

async function render(slot, page) {
  // Draw at the shown width times screen density (capped) so text stays sharp.
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(slot.clientWidth, 600) * dpr;
  const scale = width / page.getViewport({ scale: 1 }).width;
  const vp = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = Math.floor(vp.width);
  canvas.height = Math.floor(vp.height);
  slot.append(canvas);
  await page.render({ canvas, viewport: vp }).promise;
  slot.classList.add("ready");
}
