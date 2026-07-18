import httpx
from charmap import text_to_matrix

# Built-in fallback quotes
BUILTIN_QUOTES = [
    "THE ONLY WAY TO DO GREAT WORK IS TO LOVE WHAT YOU DO. - STEVE JOBS",
    "IN THE MIDDLE OF DIFFICULTY LIES OPPORTUNITY. - ALBERT EINSTEIN",
    "LIFE IS WHAT HAPPENS WHEN YOU ARE BUSY MAKING OTHER PLANS. - JOHN LENNON",
    "THE FUTURE BELONGS TO THOSE WHO BELIEVE IN THE BEAUTY OF THEIR DREAMS. - ELEANOR ROOSEVELT",
    "IT IS DURING OUR DARKEST MOMENTS THAT WE MUST FOCUS TO SEE THE LIGHT. - ARISTOTLE",
    "THE BEST TIME TO PLANT A TREE WAS 20 YEARS AGO. THE SECOND BEST TIME IS NOW.",
    "AN UNEXAMINED LIFE IS NOT WORTH LIVING. - SOCRATES",
    "SPREAD LOVE EVERYWHERE YOU GO. LET NO ONE EVER COME TO YOU WITHOUT LEAVING HAPPIER. - MOTHER TERESA",
    "WHEN YOU REACH THE END OF YOUR ROPE, TIE A KNOT IN IT AND HANG ON. - FRANKLIN D. ROOSEVELT",
    "ALWAYS REMEMBER THAT YOU ARE ABSOLUTELY UNIQUE. JUST LIKE EVERYONE ELSE. - MARGARET MEAD",
    "DO NOT GO WHERE THE PATH MAY LEAD. GO INSTEAD WHERE THERE IS NO PATH AND LEAVE A TRAIL. - EMERSON",
    "YOU WILL FACE MANY DEFEATS IN LIFE, BUT NEVER LET YOURSELF BE DEFEATED. - MAYA ANGELOU",
    "THE GREATEST GLORY IN LIVING LIES NOT IN NEVER FALLING, BUT IN RISING EVERY TIME WE FALL.",
    "IN THE END, IT IS NOT THE YEARS IN YOUR LIFE THAT COUNT. IT IS THE LIFE IN YOUR YEARS. - LINCOLN",
    "NEVER LET THE FEAR OF STRIKING OUT KEEP YOU FROM PLAYING THE GAME. - BABE RUTH",
    "LIFE IS EITHER A DARING ADVENTURE OR NOTHING AT ALL. - HELEN KELLER",
    "MANY OF LIFE'S FAILURES ARE PEOPLE WHO DID NOT REALIZE HOW CLOSE THEY WERE TO SUCCESS. - EDISON",
    "YOU HAVE BRAINS IN YOUR HEAD. YOU HAVE FEET IN YOUR SHOES. YOU CAN STEER YOURSELF ANY DIRECTION. - DR. SEUSS",
    "IF LIFE WERE PREDICTABLE IT WOULD CEASE TO BE LIFE AND BE WITHOUT FLAVOR. - ELEANOR ROOSEVELT",
    "IF YOU LOOK AT WHAT YOU HAVE IN LIFE, YOU'LL ALWAYS HAVE MORE. - OPRAH WINFREY",
]

# Per-screen rotation cursor
_quote_idx: dict[str, int] = {}


async def get_quote_matrix(rows: int, cols: int, custom_quotes: str = "",
                           screen_id: str = "main") -> list[list[int]]:
    idx = _quote_idx.get(screen_id, 0)

    # Use operator-supplied quotes when configured
    if custom_quotes.strip():
        pool = [q.strip() for q in custom_quotes.splitlines() if q.strip()]
        if pool:
            quote = pool[idx % len(pool)]
            _quote_idx[screen_id] = idx + 1
            return text_to_matrix(quote.upper(), rows, cols)

    # Try external API first
    quote = await _fetch_quote()
    if not quote:
        quote = BUILTIN_QUOTES[idx % len(BUILTIN_QUOTES)]
        _quote_idx[screen_id] = idx + 1

    return text_to_matrix(quote, rows, cols)


async def _fetch_quote() -> str:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("https://zenquotes.io/api/random")
            resp.raise_for_status()
            data = resp.json()
            q = data[0]["q"]
            a = data[0]["a"]
            return f"{q} - {a}".upper()
    except Exception:
        return ""
