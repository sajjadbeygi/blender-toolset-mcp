"""Disabled telemetry configuration for Blender Unified.

The original public source omitted this module. Status and opt-out tools
still need its interface, even with collection off. No remote credentials.
"""
from types import SimpleNamespace

telemetry_config = SimpleNamespace(
    enabled=False, max_prompt_length=0, timeout=1,
    supabase_url="", supabase_anon_key="", supabase_bucket="",
)
