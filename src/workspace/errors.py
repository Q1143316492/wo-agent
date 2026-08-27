"""工作区错误：执行管线会把 ``str(error)`` 变成 is_error 工具结果。"""


class WorkspaceError(Exception):
    """带稳定码的文件系统失败。``message`` 给模型看。"""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code
