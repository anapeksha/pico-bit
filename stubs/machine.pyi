class Pin:
    IN: int
    OUT: int
    PULL_UP: int

    def __init__(self, id: int | str, mode: int = ..., pull: int = ...) -> None: ...
    def value(self, value: int = ...) -> int: ...

class USBDevice:
    BUILTIN_NONE: int
    builtin_driver: int

    def __init__(self) -> None: ...
    def config(
        self,
        device_desc: bytes,
        config_desc: bytes,
        *,
        desc_strs: list[str],
        control_xfer_cb: object,
        open_itf_cb: object,
    ) -> None: ...
    def active(self, value: bool) -> None: ...
    def submit_xfer(self, endpoint: int, data: bytearray | bytes) -> None: ...
