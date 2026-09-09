"""Patterns enforced by the example Claude Code gate."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    pattern: re.Pattern[str]
    guidance: str


def _compile(pattern: str, *, ignore_case: bool = False) -> re.Pattern[str]:
    flags = re.VERBOSE | (re.IGNORECASE if ignore_case else 0)
    return re.compile(pattern, flags)


RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="aiscb-PRESERVE-001",
        title="TLS certificate verification disabled",
        pattern=_compile(
            r"""
              verify \s* = \s* False \b
            | rejectUnauthorized \s* : \s* false
            | InsecureSkipVerify \s* : \s* true
            | NODE_TLS_REJECT_UNAUTHORIZED \s* [=:] \s* ["']? 0 \b
            | ssl \s* \. \s* _create_unverified_context
            | CURLOPT_SSL_VERIFYPEER \s* , \s* (?: 0 | false )
            | \b curl \b [^\n]* \s (?: -[A-Za-z]*k | --insecure ) \b
            """
        ),
        guidance=(
            "Keep certificate verification enabled and configure the correct CA, "
            "hostname, or trust bundle."
        ),
    ),
    Rule(
        rule_id="aiscb-PRESERVE-001",
        title="Authentication, authorization, or CSRF behind an off switch",
        pattern=_compile(
            r"""
              \b (?: DISABLE | SKIP | BYPASS | NO ) _
                (?: AUTH | AUTHZ | AUTHENTICATION | AUTHORIZATION
                  | CSRF | XSRF | SECURITY | LOGIN | PERMISSION S? ) \b
            | \b (?: [A-Z0-9]+ _ )*
                (?: AUTH | AUTHENTICATION | AUTHORIZATION | CSRF | XSRF | SECURITY )
                _ (?: ENABLED | REQUIRED | CHECK S? ) ["']? \s* \]? \s* [=:] \s* ["']? (?: false | 0 ) \b
            """,
            ignore_case=True,
        ),
        guidance=(
            "Keep the control enabled and fix the protected path without adding a "
            "runtime bypass."
        ),
    ),
)
