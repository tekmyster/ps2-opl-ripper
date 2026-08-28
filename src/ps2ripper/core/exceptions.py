class PS2RipperError(Exception):
    """Base class for user-facing application failures."""


class CancelledError(PS2RipperError):
    """Raised after a cancellable operation acknowledges cancellation."""


class ValidationError(PS2RipperError):
    """Raised when media, an image, or a destination fails validation."""


class UnsafeDeviceError(PS2RipperError):
    """Raised when a disk cannot be proven safe for destructive access."""


class NativeCallError(PS2RipperError, OSError):
    def __init__(self, operation: str, error_code: int, message: str) -> None:
        self.operation = operation
        self.error_code = error_code
        self.system_message = message
        super().__init__(f"{operation} failed (Win32 error {error_code}): {message}")


class OpticalReadError(PS2RipperError, OSError):
    def __init__(self, lba: int, attempts: int, detail: str = "") -> None:
        self.lba = lba
        self.attempts = attempts
        suffix = f" {detail}" if detail else ""
        super().__init__(f"Optical read failed at LBA {lba:,} after {attempts} attempts.{suffix}")
