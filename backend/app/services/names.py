def normalize_player_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()
