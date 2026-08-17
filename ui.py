"""Tiny ANSI terminal UI helpers. No external deps."""
import os
import sys

def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

def _wrap(code, s):
    if not _COLOR:
        return s
    return f"\033[{code}m{s}\033[0m"

def red(s):    return _wrap("31", s)
def green(s):  return _wrap("32", s)
def yellow(s): return _wrap("33", s)
def blue(s):   return _wrap("34", s)
def magenta(s):return _wrap("35", s)
def cyan(s):   return _wrap("36", s)
def gray(s):   return _wrap("90", s)
def bold(s):   return _wrap("1", s)

RARITY_COLOR = {
    "Common": gray,
    "Uncommon": green,
    "Rare": blue,
    "Epic": magenta,
    "Legendary": yellow,
}

def rarity(name, color=None):
    c = RARITY_COLOR.get(color or name, lambda s: s)
    return c(name)

def hr(ch="─", n=64):
    return gray(ch * n)

def panel(title, lines, width=64):
    """Render a boxed panel."""
    inner = width - 4
    out = [cyan("┌─ " + title + " " + "─" * max(0, inner - len(title)))]
    for line in _wrap_lines(lines, inner):
        out.append(cyan("│  ") + line)
    out.append(cyan("└" + "─" * (width - 2)))
    return "\n".join(out)

def _wrap_lines(lines, width):
    import textwrap
    res = []
    for ln in lines:
        res.extend(textwrap.wrap(ln, width) or [""])
    return res

def say(text):
    print(text)

def dim(text):
    print(gray(text))
