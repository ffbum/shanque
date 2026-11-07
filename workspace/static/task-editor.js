function attachCalendar(form) {
  const calendar = form.querySelector(".inline-calendar");
  const days = calendar.querySelector(".calendar-days");
  const marker = calendar.querySelector(".calendar-marker");
  const due = form.elements.due;
  const start = form.elements.start_date;
  due.min = start.value;
  start.addEventListener("change", () => { due.min = start.value; });
  const node = form.elements.milestone_id;
  const planned = () => node.selectedOptions[0]?.dataset.date || "";
  const monthOf = (iso) => new Date(iso.slice(0, 7) + "-01T12:00:00Z");
  let month = monthOf(due.value || planned() || form.dataset.today);

  function draw() {
    const year = month.getUTCFullYear();
    const monthIndex = month.getUTCMonth();
    calendar.querySelector("strong").textContent = year + " 年 " + (monthIndex + 1) + " 月";
    days.replaceChildren();
    const cursor = new Date(month);
    const offset = (cursor.getUTCDay() + 6) % 7;
    for (let i = 0; i < offset; i++) days.append(document.createElement("span"));
    while (cursor.getUTCMonth() === monthIndex) {
      const iso = cursor.toISOString().slice(0, 10);
      const day = document.createElement("button");
      day.type = "button";
      day.dataset.date = iso;
      day.textContent = cursor.getUTCDate();
      day.setAttribute("aria-label", iso + (iso === planned() ? " 节点计划日" : ""));
      day.setAttribute("aria-pressed", String(iso === due.value));
      day.classList.toggle("is-node", iso === planned());
      days.append(day);
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }
    marker.hidden = !planned();
    marker.textContent = "节点计划日 · " + planned();
  }

  function showMonth(date) {
    if (date) month = monthOf(date);
    draw();
  }
  calendar.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.month) {
      month.setUTCMonth(month.getUTCMonth() + Number(button.dataset.month));
      draw();
    } else if (button === marker) {
      showMonth(planned());
    } else if (button.dataset.date) {
      due.value = button.dataset.date;
      draw();
      days.querySelector('[aria-pressed="true"]').focus();
    }
  });
  node.addEventListener("change", () => {
    if (planned()) due.value = planned();
    showMonth(due.value);
  });
  due.addEventListener("change", () => showMonth(due.value));
  calendar.hidden = false;
  draw();
}

document.querySelectorAll(".task-form").forEach(attachCalendar);
const taskEditor = document.getElementById("task-editor");
if (taskEditor) {
  let activeRequest = 0;
  taskEditor.addEventListener("close", () => { activeRequest++; });
  document.addEventListener("click", async (event) => {
    const link = event.target.closest("a[data-task-editor]");
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const requestId = ++activeRequest;
    taskEditor.textContent = "正在读取任务…";
    taskEditor.showModal();
    try {
      const url = new URL(link.href);
      url.searchParams.set("fragment", "1");
      const response = await fetch(url);
      if (!response.ok || response.redirected) throw new Error("任务表单不可用");
      const markup = await response.text();
      if (requestId !== activeRequest || !taskEditor.open) return;
      taskEditor.innerHTML = markup;
      const form = taskEditor.querySelector(".task-form");
      attachCalendar(form);
      form.elements.name.focus();
    } catch {
      if (requestId === activeRequest && taskEditor.open) location.assign(link.href);
    }
  });
}
