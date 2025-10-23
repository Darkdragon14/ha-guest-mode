from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store


def _normalize_selection(selection: str) -> tuple[str, str | None] | None:
    if not selection:
        return None
    sanitized = selection.strip()
    if not sanitized:
        return None
    sanitized = sanitized.strip("/")
    if not sanitized:
        return None
    if "/" in sanitized:
        dashboard, view = sanitized.split("/", 1)
        dashboard = (dashboard or "lovelace").strip() or "lovelace"
        view = (view or "").strip().strip("/") or None
        return (dashboard, view)
    return sanitized, None


def _group_selections(selections: Iterable[str]) -> dict[str, set[str] | None]:
    grouped: dict[str, set[str] | None] = {}
    for raw in selections:
        normalized = _normalize_selection(raw)
        if not normalized:
            continue
        dashboard, view = normalized
        if view is None:
            grouped[dashboard] = None
            continue
        if dashboard in grouped and grouped[dashboard] is None:
            continue
        if dashboard not in grouped:
            grouped[dashboard] = {view}
            continue
        cast(set[str], grouped[dashboard]).add(view)
    return grouped


def _match_view(view: dict[str, Any], target: str) -> bool:
    if not target:
        return False
    path = view.get("path")
    if isinstance(path, str) and path == target:
        return True
    view_id = view.get("id")
    if isinstance(view_id, str) and view_id == target:
        return True
    return False


def _get_visibility(view: dict[str, Any]) -> list[dict[str, Any]]:
    visibility = view.get("visibility")
    if not isinstance(visibility, list):
        return []
    return [entry for entry in visibility if isinstance(entry, dict)]


def _add_user_to_view(view: dict[str, Any], user_id: str) -> bool:
    visibility = _get_visibility(view)
    if any(entry.get("user") == user_id for entry in visibility):
        return False
    visibility.append({"user": user_id})
    view["visibility"] = visibility
    return True


def _remove_user_from_view(view: dict[str, Any], user_id: str) -> bool:
    visibility = _get_visibility(view)
    if not visibility:
        return False
    remaining = [entry for entry in visibility if entry.get("user") != user_id]
    if len(remaining) == len(visibility):
        return False
    if remaining:
        view["visibility"] = remaining
    else:
        view.pop("visibility", None)
    return True


async def _async_update_lovelace_visibility(
    hass: HomeAssistant,
    selections: Iterable[str],
    user_id: str,
    add: bool,
) -> bool:
    if not user_id:
        return False

    grouped = _group_selections(selections)
    if not grouped:
        return False

    reload_required = False

    for dashboard, views in grouped.items():
        storage_key = "lovelace" if dashboard == "lovelace" else f"lovelace.dashboard_{dashboard}"
        store = Store(hass, 1, storage_key, private=True)
        data = await store.async_load()
        if not data:
            continue

        config = data.get("data", {}).get("config")
        if not isinstance(config, dict):
            continue

        stored_views = config.get("views")
        if not isinstance(stored_views, list):
            continue

        if views is None:
            target_views = stored_views
        else:
            target_views = [
                view
                for view in stored_views
                if any(_match_view(view, view_name) for view_name in views)
            ]
            if not target_views:
                continue

        store_changed = False
        for view in target_views:
            if add:
                store_changed |= _add_user_to_view(view, user_id)
            else:
                store_changed |= _remove_user_from_view(view, user_id)

        if store_changed:
            await store.async_save(data)
            reload_required = True

    if reload_required and hass.services.has_service("lovelace", "reload"):
        await hass.services.async_call("lovelace", "reload", blocking=False)

    return reload_required


async def async_add_user_to_lovelace(
    hass: HomeAssistant, selections: Iterable[str], user_id: str
) -> bool:
    return await _async_update_lovelace_visibility(hass, selections, user_id, True)


async def async_remove_user_from_lovelace(
    hass: HomeAssistant, selections: Iterable[str], user_id: str
) -> bool:
    return await _async_update_lovelace_visibility(hass, selections, user_id, False)
