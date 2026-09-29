"""Authorization gate — no heavy/destructive module runs without explicit consent.

Policy mirrors the in-house rule: 沒有授權書就不動手 (no work without a signed
authorization). Modules marked HEAVY (vuln / load / login-storm) require BOTH:
  1. CLI flag --i-am-authorized, AND
  2. target.host listed in Target.authorized_domains
Production login-storm additionally requires --allow-prod-login-storm.
"""
from __future__ import annotations

from .config import Target, host_of

HEAVY_MODULES = {"vuln", "load", "login-storm"}


class AuthorizationError(PermissionError):
    pass


def looks_production(host: str) -> bool:
    staging_hints = ("staging", "stg", "test", "qa", "dev", "uat", "localhost", "127.0.0.1", ".local", ".internal")
    return not any(h in host for h in staging_hints)


def check(module: str, target: Target, *, authorized_flag: bool, allow_prod_storm: bool = False) -> None:
    if module not in HEAVY_MODULES:
        return
    host = host_of(target.base_url)
    if not authorized_flag:
        raise AuthorizationError(
            f"[{module}] is a HEAVY module. Re-run with --i-am-authorized after obtaining a "
            f"signed authorization covering {host}."
        )
    allowed = {d.lower().removeprefix("www.") for d in target.authorized_domains}
    if host not in allowed and "*" not in allowed:
        raise AuthorizationError(
            f"[{module}] target host '{host}' is not listed in Target.authorized_domains "
            f"{sorted(allowed)}. Update the target profile to reflect your signed scope."
        )
    if module == "login-storm" and looks_production(host) and not allow_prod_storm:
        raise AuthorizationError(
            f"'{host}' looks like PRODUCTION. Massive login storms must run against staging. "
            "Override only with written site-owner consent via --allow-prod-login-storm."
        )
