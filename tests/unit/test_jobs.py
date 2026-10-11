import pytest
from app.jobs.service import transition
from app.models import Job
from app.storage.service import LocalStorage


@pytest.mark.parametrize(
    "old,new",
    [
        ("PENDING", "RUNNING"),
        ("RUNNING", "COMPLETED"),
        ("RUNNING", "CANCEL_REQUESTED"),
        ("CANCEL_REQUESTED", "CANCELLED"),
        ("FAILED", "RETRYING"),
    ],
)
def test_allowed_transitions(old, new):
    job = Job(state=old)
    transition(job, new)
    assert job.state == new


@pytest.mark.parametrize(
    "old,new",
    [("COMPLETED", "RUNNING"), ("CANCELLED", "COMPLETED"), ("PENDING", "COMPLETED"), ("FAILED", "COMPLETED")],
)
def test_invalid_transitions(old, new):
    with pytest.raises(ValueError):
        transition(Job(state=old), new)


@pytest.mark.parametrize("key", ["../../secret", "/etc/passwd", ".."])
def test_storage_escape(key):
    with pytest.raises(ValueError):
        LocalStorage().path(key)
