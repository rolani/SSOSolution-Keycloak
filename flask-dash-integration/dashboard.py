# example of using keycloak authentication with flask and dash
import dash
from flask_oidc import OpenIDConnect
from keycloak import KeycloakOpenID

from app import app

from app.layout import app_layout



# instantiate oidc auth for app
oidc = OpenIDConnect(app)

# Configure keycloak client
keycloak_openid = KeycloakOpenID(
    server_url="http://keycloak.ms6mnj5ah.com",
    client_id="flask-app",
    realm_name="soci",
    client_secret_key="makT91mFxi7z9cLBZosDKTQ1fkM0aPPe",
)

dash_app = dash.Dash(
    __name__,
    title="My Dashboard",
    update_title="Loading...",
    server=app,
    routes_pathname_prefix="/dash/",
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
)

# require keycloak oidc login
for view_func in app.view_functions:
    if view_func.startswith(dash_app.config["routes_pathname_prefix"]):
        app.view_functions[view_func] = oidc.require_login(
            app.view_functions[view_func]
        )

dash_app.layout = app_layout
