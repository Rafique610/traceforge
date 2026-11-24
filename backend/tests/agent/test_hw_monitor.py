from traceforge.agent import hw_monitor
from traceforge.agent.hw_monitor import HwMonitor


def test_summary_takes_peaks_and_ignores_missing_gpu(monkeypatch):
    rows = iter([(1000, 10), (None, None), (4000, 90)])
    monkeypatch.setattr(hw_monitor, "read_gpu", lambda: next(rows))
    monkeypatch.setattr(hw_monitor, "read_ram_used_mib", lambda: 5000)
    m = HwMonitor()
    for _ in range(3):
        m.sample()
    s = m.summary()
    assert s["samples"] == 3
    assert s["gpu_mem_peak_mib"] == 4000 and s["gpu_util_peak_pct"] == 90
    assert s["ram_used_peak_mib"] == 5000


def test_no_gpu_gives_none(monkeypatch):
    monkeypatch.setattr(hw_monitor, "read_gpu", lambda: (None, None))
    monkeypatch.setattr(hw_monitor, "read_ram_used_mib", lambda: None)
    m = HwMonitor()
    m.sample()
    assert m.summary()["gpu_mem_peak_mib"] is None


def test_context_manager_samples_and_stops(monkeypatch):
    monkeypatch.setattr(hw_monitor, "read_gpu", lambda: (1, 1))
    monkeypatch.setattr(hw_monitor, "read_ram_used_mib", lambda: 1)
    with HwMonitor(interval_s=0.05) as m:
        pass
    assert len(m.samples) >= 1 and m._thread is not None and not m._thread.is_alive()
