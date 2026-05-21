from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://evaluation:evaluation@postgres:5432/evaluation"
    session_cookie_name: str = "s1"
    session_cookie_secure: bool = True
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_ttl_minutes: int = 360
    session_cleanup_interval_minutes: int = 60

    microsoft_tenant_id: str = "organizations"
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_path: str = "/api/v1/auth/callback/microsoft"
    microsoft_scopes: str = '["openid","email","User.Read"]'

    initialization_email: str = "bootstrap@example.com"
    company_email_domain: str = "example.com"
    frontend_success_url: str = "/"
    frontend_failure_url: str = "/login"

    @property
    def initialization_email_normalized(self) -> str:
        return self.initialization_email.strip().lower()

    @property
    def company_email_domain_normalized(self) -> str:
        return self.company_email_domain.strip().lower().lstrip("@")

    @property
    def microsoft_scope_value(self) -> str:
        scopes = parse_list_like_setting(self.microsoft_scopes)
        normalized_scopes = {scope.lower() for scope in scopes}
        if "openid" not in normalized_scopes:
            scopes.insert(0, "openid")
        if "user.read" not in normalized_scopes:
            scopes.append("User.Read")
        return " ".join(scopes)

    @property
    def microsoft_authorize_url(self) -> str:
        return f"{self.microsoft_authority_base_url}/oauth2/v2.0/authorize"

    @property
    def microsoft_token_url(self) -> str:
        return f"{self.microsoft_authority_base_url}/oauth2/v2.0/token"

    @property
    def microsoft_authority_base_url(self) -> str:
        tenant = self.microsoft_tenant_id.strip() or "organizations"
        if tenant.startswith("http://") or tenant.startswith("https://"):
            return tenant.rstrip("/")
        return f"https://login.microsoftonline.com/{tenant}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def parse_list_like_setting(value: str) -> list[str]:
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    return [
        item.strip().strip('"').strip("'")
        for item in stripped.split(",")
        if item.strip().strip('"').strip("'")
    ]
