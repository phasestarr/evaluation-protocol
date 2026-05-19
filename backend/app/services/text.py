def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
