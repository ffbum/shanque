document.addEventListener("click", (event) => {
  const trigger = event.target.closest(
    "[data-open],[data-dismiss],[data-confirm]",
  );
  if (!trigger) return;
  if (trigger.hasAttribute("data-confirm") && !confirm(trigger.dataset.confirm))
    event.preventDefault();
  if (trigger.dataset.open) {
    const dialog = document.getElementById(trigger.dataset.open);
    if (trigger.dataset.nextState) {
      const state = trigger.dataset.nextState;
      const form = dialog.querySelector("form");
      form.elements.status.value = state;
      const note = form.elements.note;
      note.value = trigger.closest("[data-task]").dataset.state === state ? note.defaultValue : "";
      note.required = state === "受阻";
      dialog.querySelector("[data-status-title]").textContent = " · " + state;
      dialog.showModal();
      note.focus();
    } else {
      dialog.showModal();
    }
  }
  if (trigger.hasAttribute("data-dismiss")) trigger.closest("dialog").close();
});
document.querySelectorAll('select[name="status"]').forEach((select) => {
  select.addEventListener("change", () => {
    select.form.elements.note.required = select.value === "受阻";
  });
});
const search = document.querySelector("#project-search");
if (search) {
  let state = "全部项目";
  const buttons = document.querySelectorAll("[data-filter]");
  const syncChildren = (row) => {
    const toggle = row.querySelector(".tree-toggle");
    document.getElementById(toggle.getAttribute("aria-controls")).hidden =
      row.hidden || toggle.getAttribute("aria-expanded") !== "true";
  };
  document.querySelectorAll(".tree-toggle").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      toggle.setAttribute("aria-expanded", String(toggle.getAttribute("aria-expanded") !== "true"));
      syncChildren(toggle.closest("[data-project]"));
    });
  });
  const filter = () => {
    let total = 0;
    for (const row of document.querySelectorAll("[data-project]")) {
      row.hidden =
        (state !== "全部项目" && state !== row.dataset.state) ||
        !row.dataset.search
          .toLowerCase()
          .includes(search.value.trim().toLowerCase());
      if (!row.hidden) total++;
      syncChildren(row);
    }
    document.querySelector("#empty-projects").hidden = total > 0;
  };
  for (const button of buttons)
    button.addEventListener("click", () => {
      state = button.dataset.filter;
      for (const item of buttons)
        item.setAttribute("aria-pressed", String(item === button));
      filter();
    });
  search.addEventListener("input", filter);
}
const taskFilter = document.querySelector("#task-filter");
if (taskFilter) {
  const filter = () => {
    let total = 0;
    const state = taskFilter.value;
    for (const row of document.querySelectorAll("[data-task]")) {
      const visible =
        state === "全部任务" ||
        state === row.dataset.state ||
        (state === "待办理" && row.dataset.state !== "已完成") ||
        (state === "逾期" && row.dataset.late === "1");
      row.hidden = !visible;
      if (visible) total++;
    }
    document.querySelector("#empty-tasks").hidden = total > 0;
  };
  taskFilter.addEventListener("change", filter);
  filter();
}
