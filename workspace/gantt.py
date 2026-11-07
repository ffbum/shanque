"""Build a shared date scale from the milestones the viewer can see."""

from datetime import date

DAY_WIDTH = 24


def _day(value):
    return date.fromisoformat(value[:10]).toordinal()


def build_chart(projects, as_of):
    current = as_of.toordinal()
    dates = [current]
    counts = {"total": 0, "done": 0, "risk": 0, "upcoming": 0}
    for project in projects:
        dates.extend(_day(d) for d in (project["start_date"], project["end_date"]) if d)
        dates.extend(_day(t["start_date"]) for t in project["tasks"] if t["start_date"])
        dates.extend(_day(task["due"]) for task in project["tasks"])
        project["unlinked"] = [t for t in project["tasks"] if t["milestone_id"] is None]
        for node in project["milestones"]:
            plan = _day(node["planned"])
            dates.append(plan)
            end = _day(node["achieved"]) if node["achieved"] else None
            forecast = _day(node["forecast"]) if node["forecast"] else None
            dates.extend(d for d in (end, forecast) if d is not None)
            remaining = plan - current
            late = forecast - plan if forecast else 0
            if end:
                diff = end - plan
                label = (
                    f"晚 {diff} 天达成"
                    if diff > 0
                    else (f"提前 {-diff} 天达成" if diff < 0 else "按期达成")
                )
                state = "done"
            elif remaining < 0:
                state, label = "risk", f"逾期 {-remaining} 天"
            elif late > 0:
                state, label = "risk", f"预计晚 {late} 天"
            else:
                state = "pending"
                label = "今日到期" if remaining == 0 else f"还有 {remaining} 天"
            counts["total"] += 1
            counts["done"] += state == "done"
            counts["risk"] += state == "risk"
            counts["upcoming"] += not end and 0 <= remaining <= 7
            node.update(state=state, label=label)

    # Align the origin to Monday. All rows then share the same weekly grid.
    start = max(date.min.toordinal(), min(dates) - 3)
    start -= date.fromordinal(start).weekday()
    stop = min(date.max.toordinal(), max(max(dates) + 3, start + 42))

    def position(day):
        return (day - start) * DAY_WIDTH

    for project in projects:
        for task in project["tasks"]:
            task["due_x"] = position(_day(task["due"]))
            task["start_x"] = position(_day(task["start_date"])) if task["start_date"] else None
        for node in project["milestones"]:
            plan = position(_day(node["planned"]))
            forecast = position(_day(node["forecast"])) if node["forecast"] else None
            actual = position(_day(node["achieved"])) if node["achieved"] else None
            node["stage_x"] = position(_day(node["stage_start"])) if node["stage_start"] else None
            # Show elapsed lateness even when a revised forecast is missing.
            last = actual if actual is not None else forecast
            if last is None and node["state"] == "risk":
                last = position(current)
            segment = [x for x in (plan, forecast, last) if x is not None]
            node.update(
                plan_x=plan,
                forecast_x=forecast,
                actual_x=actual,
                left=min(segment),
                width=max(segment) - min(segment),
            )
        if project["start_date"] and project["end_date"]:
            project["left"] = position(_day(project["start_date"]))
            project["width"] = position(_day(project["end_date"])) - project["left"]

    return {
        "counts": counts,
        "day_width": DAY_WIDTH,
        "width": position(stop) + DAY_WIDTH,
        "today_x": position(current),
        "start": date.fromordinal(start),
        "stop": date.fromordinal(stop),
    }
