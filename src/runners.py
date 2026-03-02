from __future__ import annotations

from json import loads, dumps

from .env_types import Variable, BlockType, BaseEnvironment, HexValue


def split_by_not_in_blocks_or_strings(text: str, sep: str = " "):
    """
    Split `text` by `sep` but ignore separators inside:
    - single or double quotes
    - blocks `( ... )` outside quotes
    Handles escaped quotes and separators.
    """
    result = []
    buf = []
    depth = 0
    in_quote = None
    escape = False

    for c in text:
        if escape:
            buf.append(c)
            escape = False
            continue

        if c == "\\":
            buf.append(c)
            escape = True
            continue
        if in_quote:
            buf.append(c)
            if c == in_quote:
                in_quote = None
            continue
        elif c in ("'", '"'):
            buf.append(c)
            in_quote = c
            continue
        if c == "(":
            depth += 1
            buf.append(c)
            continue
        if c == ")":
            depth = max(depth - 1, 0)
            buf.append(c)
            continue
        if c == sep and depth == 0 and not in_quote:
            result.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)

    if buf:
        result.append("".join(buf).strip())
    return result


class BaseRunner:
    """Base Runner is used ONLY to create other Runner classes"""

    COMMANDS = {}

    def __init__(self, val: str = "", args=None, env: BaseEnvironment | None = None):
        """
        Initialize a Runner instance.
        """
        self._value = val
        self._args = args if args is not None else []
        self.env = env if env is not None else BaseEnvironment()

    @staticmethod
    def floating(val) -> bool:
        """Check if a value can be converted to a float."""
        try:
            float(val)
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def hexable(val) -> bool:
        """Check if a value can be converted to a hexadecimal integer."""
        try:
            int(val, 16)
            return True
        except (TypeError, ValueError):
            return False

    def to_type(self, s: str):
        """
        Convert a string representation into its corresponding Python type or custom object.
        """
        if not isinstance(s, str):
            return s

        if len(s) >= 2 and s.startswith('"') and s[-1] == '"':
            return s[1:-1]
        elif s.isdigit():
            return int(s)
        elif self.floating(s):
            return float(s)
        elif len(s) >= 2 and s[0] in {"{", "["} and s[-1] in {"}", "]"}:
            return loads(s)
        elif s[:2] == "0x" and self.hexable(s[2:]):
            return HexValue(int(s[2:], 16))
        elif self.hexable(s):
            return HexValue(int(s, 16))
        elif len(s) >= 2 and s.startswith("(") and s[-1] == ")":
            return BlockType(s)
        else:
            return Variable(s)

    def from_type(self, s):
        """
        Convert a value to a string representation based on its type.
        """
        ts = type(s)
        if ts in {str, HexValue, float, int, BlockType}:
            return str(s)
        elif ts in {dict, list}:
            return dumps(s, ensure_ascii=False)
        return str(s)
    @classmethod
    def register_as_command(cls, name: str):
        """
        Decorator that registers a function as a command for a specific language runner.
        """
        if cls is BaseRunner:
            raise TypeError("BaseRunner can't be used as a specific language runner")

        def decorator(func):
            cls.COMMANDS[name] = func
            return func

        return decorator
    @classmethod
    def from_string(cls, s: str, env: BaseEnvironment):
        """
        Create an instance from a string representation: "callable arg1 arg2 ..."
        """
        sp = split_by_not_in_blocks_or_strings(s)
        temp = cls("", [], BaseEnvironment())
        all_args = [temp.to_type(i) for i in sp[1:]]
        return cls(sp[0], all_args, env)

    def run(self, error: bool = False):
        """
        Execute a command from the COMMANDS registry based on the stored value and arguments.
        """
        try:
            self.COMMANDS[self._value](*self._args, env=self.env)
        except Exception:
            if error:
                raise
