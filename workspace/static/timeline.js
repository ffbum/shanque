const projectSelect = document.querySelector("#tl-project");
const riskOnly = document.querySelector("#tl-risk");
const fold = document.querySelector("#tl-fold");
const groups = [...document.querySelectorAll(".tl-group")];

function setExpanded(toggle, expanded) {
  toggle.setAttribute("aria-expanded", String(expanded));
  document.getElementById(toggle.getAttribute("aria-controls")).hidden = !expanded;
}

function refreshFold() {
  const visible = groups.filter(group => !group.hidden);
  fold.disabled = !visible.length;
  fold.textContent = visible.some(group => !group.querySelector(".tl-nodes").hidden)
    ? "全部收起" : "全部展开";
}

function filterChart() {
  for (const group of groups) {
    const nodes = [...group.querySelectorAll(".tl-branch")];
    for (const node of nodes) node.hidden = riskOnly.checked && node.dataset.state !== "risk";
    group.hidden = (projectSelect.value && group.dataset.projectId !== projectSelect.value)
      || (riskOnly.checked && !nodes.some(node => !node.hidden));
    if (riskOnly.checked && !group.hidden) setExpanded(group.querySelector(".tl-toggle"), true);
  }
  document.querySelector("#tl-empty").hidden = groups.some(group => !group.hidden);
  refreshFold();
}

for (const group of groups) {
  group.addEventListener("click", (event) => {
    let toggle = event.target.closest("button[aria-controls]");
    if (!toggle && event.target.closest("[data-toggle-branch]")) {
      toggle = event.target.closest(".tl-branch").querySelector(".tl-branch-toggle");
    }
    if (!toggle) return;
    setExpanded(toggle, toggle.getAttribute("aria-expanded") !== "true");
    refreshFold();
  });
}
fold.addEventListener("click", () => {
  const visible = groups.filter(group => !group.hidden);
  const expand = visible.every(group => group.querySelector(".tl-nodes").hidden);
  for (const group of visible) {
    for (const toggle of group.querySelectorAll("button[aria-controls]")) setExpanded(toggle, expand);
  }
  refreshFold();
});
projectSelect.addEventListener("change", filterChart);
riskOnly.addEventListener("change", filterChart);
filterChart();

// Render date labels only for the visible stretch of a multi-year schedule.
const viewport = document.querySelector(".tl-scroll");
const axis = document.querySelector(".tl-axis .tl-lane");
const labels = axis.querySelector(".tl-ticks");
const dayWidth = Number(axis.dataset.dayWidth);
const origin = Date.parse(axis.dataset.start + "T00:00:00Z");
let previousRange = "";

function renderDates() {
  const first = Math.max(0, Math.floor(viewport.scrollLeft / dayWidth) - 7);
  const last = Math.min(Math.ceil(axis.clientWidth / dayWidth) - 1,
    Math.ceil((viewport.scrollLeft + viewport.clientWidth) / dayWidth) + 7);
  const range = first + "/" + last;
  if (range === previousRange) return;
  previousRange = range;
  const fragment = document.createDocumentFragment();
  for (let offset = first; offset <= last; offset++) {
    const date = new Date(origin + offset * 86400000);
    const day = document.createElement("span");
    day.className = "tl-day";
    day.style.left = offset * dayWidth + "px";
    day.textContent = date.getUTCDate();
    fragment.append(day);
    if (offset % 7 === 0) {
      const week = document.createElement("span");
      week.className = "tl-tick";
      week.style.left = offset * dayWidth + 3 + "px";
      week.textContent = date.toISOString().slice(0, 10);
      fragment.append(week);
    }
  }
  labels.replaceChildren(fragment);
}

let drag = null;
axis.addEventListener("pointerdown", (event) => {
  if (!event.isPrimary || event.button !== 0 || viewport.scrollWidth <= viewport.clientWidth) return;
  drag = { id: event.pointerId, x: event.clientX, left: viewport.scrollLeft };
  axis.setPointerCapture(event.pointerId);
  axis.classList.add("is-dragging");
});
axis.addEventListener("pointermove", (event) => {
  if (drag?.id === event.pointerId) viewport.scrollLeft = drag.left + drag.x - event.clientX;
});
function finishDrag(event) {
  if (drag?.id !== event.pointerId) return;
  drag = null;
  axis.classList.remove("is-dragging");
  if (axis.hasPointerCapture(event.pointerId)) axis.releasePointerCapture(event.pointerId);
}
axis.addEventListener("pointerup", finishDrag);
axis.addEventListener("pointercancel", finishDrag);
axis.addEventListener("lostpointercapture", finishDrag);

function resizeChart() {
  axis.classList.toggle("is-scrollable", viewport.scrollWidth > viewport.clientWidth);
  const lastDay = Math.ceil(axis.clientWidth / dayWidth) - 1;
  const end = document.querySelector("#tl-axis-end");
  end.dateTime = new Date(origin + lastDay * 86400000).toISOString().slice(0, 10);
  end.textContent = end.dateTime;
  renderDates();
}
viewport.addEventListener("scroll", renderDates, {passive: true});
new ResizeObserver(resizeChart).observe(viewport);
function locateToday() {
  const header = axis.parentElement;
  const visibleWidth = viewport.clientWidth - header.firstElementChild.offsetWidth
    - header.lastElementChild.offsetWidth;
  const todayX = parseFloat(getComputedStyle(axis).getPropertyValue("--today"));
  viewport.scrollLeft = todayX - visibleWidth / 2;
}
document.querySelector("#tl-locate").addEventListener("click", locateToday);
resizeChart();
locateToday();
