"""Public Zanim error types with user-facing diagnostics."""


class ZanimError(RuntimeError):
    """Base class for runtime failures raised by Zanim itself."""


class NativeError(ZanimError):
    """The bundled/native renderer could not be loaded or is incompatible."""


class MediaError(ZanimError):
    """An external media dependency or media operation failed."""


class PreviewError(ZanimError):
    """The local preview server could not complete an operation."""
