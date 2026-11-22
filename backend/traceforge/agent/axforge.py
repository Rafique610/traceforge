"""AxForge profile: only `glm-5.3-flash` on the fixed base URL, one attempt, no fallback.

The website host is `glm-5-3-flash.axforge.ai`; the API model id is `glm-5.3-flash` (with a dot).
The same key can call other (prepaid) models, and AxForge exposes no field that separates the free
allowance from paid balance, so the id and host are locked here and every error stops the caller.
The free 3M tokens/30 days are only safe while the account's prepaid balance is zero (402 then
means the allowance is used up).
"""

MODEL = "glm-5.3-flash"
BASE_URL = "https://api.axforge.ai/v1"  # fixed; no configurable URL, no fallback host


class AxForgeRefused(RuntimeError):
    """A request for any other model id was refused before sending."""


def guard_model(model: str) -> None:
    if model != MODEL:  # exact match: no prefix, case change, or the hyphenated website spelling
        raise AxForgeRefused(
            f"axforge: only the exact model id '{MODEL}' may be sent (refused {model!r})"
        )
