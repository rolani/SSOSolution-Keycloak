import os
from distutils.util import strtobool

from flask import Flask

USE_TEST_DB = strtobool(os.environ.get("TESTING", "True"))


app = Flask(__name__)
app.config["SECRET_KEY"] = "5ret7346trg378tgwei7"
app.config["OIDC_CLIENT_SECRETS"] = "./client.json"
app.config["OIDC_ID_TOKEN_COOKIE_SECURE"] = False
app.config["OIDC_REQUIRE_VERIFIED_EMAIL"] = True
app.config["OIDC_USER_INFO_ENABLED"] = True
app.config["OIDC_SCOPES"] = ["openid", "email", "profile"]
app.config["OIDC_INTROSPECTION_AUTH_METHOD"] = "client_secret_post"
app.config["OIDC_TOKEN_TYPE_HINT"] = "access_token"
app.config["OIDC_CLOCK_SKEW"] = 560
