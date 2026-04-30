"""
Exception hierarchy shared across parsing and execution.
"""


class RestartPayload(Exception):
    pass


class StopPayload(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value):
        super().__init__('return')
        self.value = value


class DuckyScriptError(Exception):
    def __init__(self, line_no, message):
        super().__init__(f'Line {line_no}: {message}')
        self.line_no = line_no
        self.message = message


class DuckyParseError(DuckyScriptError):
    pass


class DuckyRuntimeError(DuckyScriptError):
    pass


class UnsafeFeatureError(DuckyRuntimeError):
    pass
