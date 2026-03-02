from __future__ import annotations

from flask_socketio import emit


class BaseEnvironment:
    """
    BaseEnvironment class for managing variables and output in a conversational environment.

    It tracks variables, the last computed value, and all outputs.
    """

    def __init__(self):
        self._vars: dict[str, object] = {}
        self.last: object = ""
        self.chat: list[str] = []

    def output(self, x):
        """
        Output a value to the server and append it to the chat history.
        """
        try:
            emit("server", str(x))
        except RuntimeError:
            pass

        self.chat.append(str(x))
        self.last = x

    def get(self, name):
        """
        Retrieve the value of a variable by name and update the last accessed variable.
        """
        self.last = self._vars[name]
        return self.last

    def set(self, name, value):
        """Set a variable in the environment."""
        self._vars[name] = value


class CEnvironment(BaseEnvironment):
    def __init__(self):
        super().__init__()
        self.heap = [{"value": None, "free": True} for _ in range(255)]
        self._first_free = 1

    def alloc(self, amount: int):
        # Find first free slot safely
        while self._first_free < len(self.heap) and not self.heap[self._first_free]["free"]:
            self._first_free += 1

        if self._first_free >= len(self.heap):
            return None  # out of heap slots

        self.heap[self._first_free]["free"] = False
        self.heap[self._first_free]["value"] = [None for _ in range(amount)]

        addr = self._first_free
        self._first_free = 1  # next allocation searches from start
        return hex(addr)[2:]  # without 0x

    def free(self, addr):
        addr_i = int(addr, 16)
        self.heap[addr_i]["free"] = True
        self.heap[addr_i]["value"] = None
        self._first_free = addr_i

    def heapget(self, addr, inneraddr):
        value = self.heap[int(addr, 16)]["value"][int(inneraddr, 16)]
        self.last = value
        return value

    def heapset(self, addr, inneraddr, value):
        self.heap[int(addr, 16)]["value"][int(inneraddr, 16)] = value


class BaseEnvType:
    """Base class for environment types."""

    def __init__(self, value):
        self.value = value

    def __int__(self):
        return int(self.value)

    def __str__(self):
        return str(self.value)


class Variable(BaseEnvType):
    """Represents a variable in the environment type system."""
    pass


class BlockType(BaseEnvType):
    """Represents a block in the environment type system."""

    @property
    def converted(self) -> str:
        return self.value[1:-1]


class HexValue(BaseEnvType):
    """A class representing hexadecimal values."""

    @property
    def as_hex(self) -> str:
        return hex(self.value)
