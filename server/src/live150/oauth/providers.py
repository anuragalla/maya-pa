from dataclasses import dataclass, field


@dataclass
class OAuthProvider:
    name: str
    auth_url: str
    token_url: str
    scopes: list[str]
    client_id_env: str
    client_secret_env: str
    revoke_url: str | None = None
    extra_auth_params: dict[str, str] = field(default_factory=dict)
    version: int = 1  # bump to trigger re-consent for existing users


PROVIDERS: dict[str, OAuthProvider] = {
    "google": OAuthProvider(
        name="google",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=[
            "openid",
            "email",
            "https://www.googleapis.com/auth/calendar",
        ],
        version=3,  # bumped: use full calendar scope for sub-calendar creation
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
        client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
        revoke_url="https://oauth2.googleapis.com/revoke",
        extra_auth_params={"access_type": "offline", "prompt": "consent"},
    ),
    # future: "fitbit", "apple_health", etc.
}
