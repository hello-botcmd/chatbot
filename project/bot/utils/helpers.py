def fmt_uptime(secs: int) -> str:
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, s   = divmod(rem, 60)
    parts  = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def trim_history(history: list, max_turns: int) -> list:
    cap = max_turns * 2
    h   = list(history[-cap:]) if len(history) > cap else list(history)
    while h and h[0].get("role") != "user":
        h = h[1:]
    return h


def is_admin(user_id: int, admin_ids: list) -> bool:
    return user_id in admin_ids


def credits_text(c: dict) -> str:
    if "error" in c:
        return f"Unavailable ({c['error'][:50]})"
    used  = f"${c['used']:.4f}"
    limit = f"${c['limit']:.4f}" if c.get("limit") is not None else "Unlimited"
    left  = f"${c['remaining']:.4f}" if c.get("remaining") is not None else "∞"
    return f"Used {used} / {limit}  —  Left: {left}"


# alias used by new code
def credits_line(c: dict) -> str:
    return credits_text(c)
