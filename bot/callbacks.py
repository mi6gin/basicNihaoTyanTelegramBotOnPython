from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Callback:
    action: str
    owner_id: int
    value: str | None = None

    def pack(self) -> str:
        parts = [self.action, str(self.owner_id)]
        if self.value is not None:
            parts.append(self.value)
        return ":".join(parts)

    @classmethod
    def unpack(cls, value: str | None) -> "Callback | None":
        parts = (value or "").split(":", maxsplit=2)
        if len(parts) < 2 or not parts[1].isdigit():
            return None
        return cls(parts[0], int(parts[1]), parts[2] if len(parts) == 3 else None)
