from charmap import text_to_matrix, blank_matrix

# Per-screen rotation cursor
_msg_idx: dict[str, int] = {}


async def get_text_matrix(rows: int, cols: int, messages: list,
                          screen_id: str = "main") -> list[list[int]]:
    if not messages:
        return blank_matrix(rows, cols)

    idx = _msg_idx.get(screen_id, 0)
    msg = messages[idx % len(messages)]
    _msg_idx[screen_id] = idx + 1

    text = msg.get("text", "")
    return text_to_matrix(text, rows, cols)
