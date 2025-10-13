import jwt
import sqlite3
from datetime import timedelta, datetime
from aiohttp import web
from typing import Any
import json

from homeassistant.core import HomeAssistant
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.translation import async_get_translations

from .const import DATABASE, DOMAIN

class ValidateTokenView(HomeAssistantView):
    name = "guest-mode:login"
    requires_auth = False

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.url = hass.data.get("get_path_to_login")

    def get_translations(self, translations: dict[str, Any], label: str):
        key = f"component.{DOMAIN}.entity.guest_error.{label}.name"
        return translations.get(key, f"Missing translation: {key}")

    async def _restore_managed_user(self, cursor, token_row: sqlite3.Row):
        available_groups = []
        store = getattr(self.hass.auth, "_store", None)
        if store is not None:
            getter = getattr(store, "async_get_groups", None)
            if getter is not None:
                available_groups = await getter()

        if not available_groups:
            getter = getattr(self.hass.auth, "async_get_group", None)
            if getter is not None:
                for group_id in ("system-admin", "system-users", "system-read-only"):
                    group = await getter(group_id)
                    if group is not None:
                        available_groups.append(group)

        available_group_ids = {group.id for group in available_groups}

        stored_groups = token_row["managed_user_groups"]
        group_ids: list[str] = []
        if stored_groups:
            try:
                parsed = json.loads(stored_groups)
                if isinstance(parsed, list):
                    group_ids = [gid for gid in parsed if gid in available_group_ids]
            except (ValueError, TypeError):
                group_ids = []

        default_group = "system-users"
        if len(group_ids) > 1 and default_group in group_ids:
            group_ids = [gid for gid in group_ids if gid != default_group]
        if not group_ids and default_group in available_group_ids:
            group_ids.append(default_group)

        group_ids = list(dict.fromkeys(group_ids))

        user_name = token_row["managed_user_name"] or token_row["token_name"] or "Guest"

        try:
            user = await self.hass.auth.async_create_user(user_name, group_ids=group_ids or None)
        except ValueError:
            return None

        cursor.execute(
            "UPDATE tokens SET userId = ?, managed_user_name = ?, managed_user_groups = ? WHERE id = ?",
            (user.id, user.name, json.dumps(group_ids) if group_ids else None, token_row["id"]),
        )
        return user

    async def get(self, request):
        language = self.hass.config.language 
        translations = await async_get_translations(self.hass, language, "entity")

        token_param = request.query.get("token")
        if not token_param:
            return web.Response(status=400, text=self.get_translations(translations, "missing_token"))
        
        conn = sqlite3.connect(self.hass.config.path(DATABASE))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM tokens WHERE uid = ?',
            (token_param,)
        )
        result = cursor.fetchone()

        
        if result is None:
            return web.Response(status=404, text=self.get_translations(translations, "token_not_found"))

        try:
            first_used = result["first_used"]
            times_used = result["times_used"] or 0
            usage_limit = result["usage_limit"]
            if usage_limit is not None and usage_limit > 0 and times_used >= usage_limit:
                return web.Response(status=403, text=self.get_translations(translations, "usage_limit_reached"))
            
            now_iso = datetime.now().isoformat()
            new_times_used = times_used + 1
            
            update_query = "UPDATE tokens SET last_used = ?, times_used = ?"
            params = [now_iso, new_times_used]

            if not first_used:
                update_query += ", first_used = ?"
                params.append(now_iso)
            
            update_query += " WHERE id = ?"
            params.append(result["id"])

            cursor.execute(update_query, tuple(params))
            conn.commit()
        except (ValueError, IndexError):
            # Columns not present, do nothing
            pass

        try:
            public_key = self.hass.data.get("public_key")
            if public_key is None:
                return web.Response(status=500, text=self.get_translations(translations, "internal_server_error"))
            decoded_token = jwt.decode(result["token_ha_guest_mode"], public_key, algorithms=["RS256"])
            is_never_expire = bool(result["is_never_expire"])
            start_date = None
            end_date = None
            if not is_never_expire:
                start_date = datetime.fromisoformat(decoded_token.get("startDate"))
                end_date = datetime.fromisoformat(decoded_token.get("endDate"))
        except jwt.ExpiredSignatureError:
            return web.Response(status=401, text=self.get_translations(translations, "expired_token"))
        except jwt.InvalidTokenError:
            return web.Response(status=401, text=self.get_translations(translations, "invalid_token"))
        except Exception as e:
            return web.Response(status=400, text=str(e))

        now = datetime.now()
        if not is_never_expire and (now < start_date or now > end_date):
            return web.Response(status=403, text=self.get_translations(translations, "not_yet_or_expired"))
        
        token = result["token_ha"]
        if token:
            refresh_token = self.hass.auth.async_validate_access_token(token)
            if refresh_token is None:
                token = ""
        else:
            token = "" 

        dashboard = result["dashboard"]
        if dashboard and dashboard.startswith('/'):
            dashboard = dashboard[1:]
        
        if token == "" and (is_never_expire or (start_date and now > start_date)):
            """ if is_never_expire or (start_date and now > start_date): """
            users = await self.hass.auth.async_get_users()

            user = next((u for u in users if u.id == result["userId"]), None)
            if user is None and result["managed_user"]:
                user = await self._restore_managed_user(cursor, result)
                if user:
                    conn.commit()
                    users = await self.hass.auth.async_get_users()

            if user is None:
                return web.Response(status=404, text=self.get_translations(translations, "user_not_found"))
            
            token_args = {
                "client_name": result["token_name"],
                "token_type": TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
            }
            if not is_never_expire and end_date:
                endDateInSeconds = (end_date - now).total_seconds()
                token_args["access_token_expiration"] = timedelta(seconds=endDateInSeconds)

            try:
                refresh_token = await self.hass.auth.async_create_refresh_token(
                    user,
                    **token_args
                )
            except ValueError:
                refresh_token = next(
                    (rt for rt in user.refresh_tokens.values() if rt.client_name == result["token_name"]),
                    None,
                )
                if refresh_token is None:
                    return web.Response(status=500, text=self.get_translations(translations, "internal_server_error"))

            token = self.hass.auth.async_create_access_token(refresh_token)

            query = """
                UPDATE tokens SET token_ha_id = ?, token_ha = ? WHERE id = ?
            """
            cursor.execute(query, (refresh_token.id, token, result["id"]))
            conn.commit()


        conn.close()

        html_content = f"""
        <!DOCTYPE html>
        <html>
            <body>
                <script type="text/javascript">
                    const hassUrl = window.location.protocol + '//' + window.location.host;
                    const access_token = '{token}';
                    localStorage.setItem('hassTokens', JSON.stringify({{ access_token: access_token, hassUrl: hassUrl }}));
                    window.location.href = hassUrl + '/{dashboard}';
                </script>
            </body>
        </html>
        """
        return web.Response(content_type="text/html", text=html_content)
