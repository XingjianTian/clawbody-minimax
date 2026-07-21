from reachy_mini_openclaw.host_bridge.log_store import LogStore
from reachy_mini_openclaw.host_bridge.models import DevicePhase, DeviceStatus


def test_device_status_serializes_stable_phase_values():
    status = DeviceStatus(phase=DevicePhase.HEALTHCHECKING)

    assert status.model_dump(mode="json")["phase"] == "healthchecking"


def test_log_store_bounds_history_and_redacts_secrets():
    store = LogStore(limit=2)
    store.append("info", "first")
    store.append("info", "Authorization: Bearer secret-token")
    store.append("error", "MINIMAX_API_KEY=sk-private")

    result = store.after(0)

    assert len(result["items"]) == 2
    assert "secret-token" not in str(result)
    assert "sk-private" not in str(result)
    assert "[REDACTED]" in str(result)


def test_log_store_append_return_cannot_mutate_stored_entry():
    store = LogStore()
    returned_entry = store.append("info", "original message")
    stored_result = store.after(0)

    returned_entry.id = 999
    returned_entry.message = "changed message"

    assert store.after(0) == stored_result
