from charmap import text_to_matrix, blank_matrix

_msg_idx: int = 0


async def get_text_matrix(rows: int, cols: int, messages: list) -> list[list[int]]:
    global _msg_idx

    if not messages:
        return blank_matrix(rows, cols)

    msg = messages[_msg_idx % len(messages)]
    _msg_idx += 1

    text = msg.get("text", "")
    return text_to_matrix(text, rows, cols)
