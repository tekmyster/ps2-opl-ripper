import pytest

from ps2ripper.core.cancellation import CancellationToken
from ps2ripper.core.exceptions import CancelledError


def test_cancellation_is_deferred_during_critical_section():
    token = CancellationToken()
    with pytest.raises(CancelledError), token.critical_section():
        token.request()
        token.checkpoint()
