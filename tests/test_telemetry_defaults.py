"""Regression for integrated assets telemetry defaults."""

import subprocess
import sys


def test_assets_opt_out_works_without_private_config_or_tracking_id():
    code = """
from blender_unified.engines.assets.telemetry import get_telemetry
collector = get_telemetry()
assert collector.config.enabled is False
assert collector._customer_uuid == 'disabled'
assert collector.config.supabase_url == ''
collector.invalidate_consent_cache()
collector.record_event('test')
assert collector._queue.empty()
"""
    subprocess.run([sys.executable, "-c", code], check=True, timeout=15)
