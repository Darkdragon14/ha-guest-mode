import jwt
import sqlite3
from datetime import datetime
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

DATABASE = "/config/custom_components/virtual_keys/virtual_keys.db"
SECRET_KEY = "information"  # Clé de signature pour le JWT

class ValidateTokenView(HomeAssistantView):
    url = "/virtual_keys/login"
    name = "virtual_keys:login"
    requires_auth = False  # Pas besoin d'authentification Home Assistant pour cette route

    async def get(self, request):
        # Récupérer le paramètre token de l'URL
        token_param = request.query.get("token")
        if not token_param:
            return web.Response(status=400, text="Token is missing")

        # Décoder le token JWT
        try:
            decoded_token = jwt.decode(token_param, SECRET_KEY, algorithms=["HS256"])
            user_id = decoded_token.get("userId")
            start_date = datetime.fromisoformat(decoded_token.get("startDate"))
            end_date = datetime.fromisoformat(decoded_token.get("endDate"))
        except jwt.ExpiredSignatureError:
            return web.Response(status=401, text="Token has expired")
        except jwt.InvalidTokenError:
            return web.Response(status=401, text="Invalid token")
        except Exception as e:
            return web.Response(status=400, text=str(e))

        # Vérifier les dates
        now = datetime.now()
        if now < start_date or now > end_date:
            return web.Response(status=403, text="Token not yet valid or expired")

        # Rechercher dans la base de données si le token existe pour l'utilisateur
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM tokens WHERE userId = ? AND token_virtual_key = ?',
            (user_id, token_param)
        )
        result = cursor.fetchone()
        conn.close()

        if result is None:
            return web.Response(status=404, text="Token not found or invalid for this user")
        
        # @Todo case where token is not set
        if result[6] == "":
          a = 2 

        # Générer la page HTML si le token est valide
        html_content = f"""
        <!DOCTYPE html>
        <html>
          <body>
            <script type="text/javascript">
              const hassUrl = window.location.protocol + '//' + window.location.host;
              const access_token = '{result[6]}';
              console.log('access_token', access_token);
              localStorage.setItem('hassTokens', JSON.stringify({{ access_token: access_token, hassUrl: hassUrl }}));
              window.location.href = hassUrl;
            </script>
          </body>
        </html>
        """
        return web.Response(content_type="text/html", text=html_content)
