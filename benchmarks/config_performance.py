#!/usr/bin/env python3
"""Performance benchmarks for PR #20 config implementation.

Run this script to measure the actual performance impact of the dependency
injection pattern introduced in PR #20.

Usage:
    python benchmarks/config_performance.py
"""

import sys
import timeit
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from inkwell.config.schema import (
    ExtractionConfig,
    GlobalConfig,
    InterviewConfig,
    TranscriptionConfig,
)


def benchmark_config_validation():
    """Benchmark config object creation and validation."""
    print("=" * 70)
    print("Config Validation Performance")
    print("=" * 70)

    # Test 1: GlobalConfig with defaults
    time_default = (
        timeit.timeit(
            "GlobalConfig()",
            setup="from inkwell.config.schema import GlobalConfig",
            number=10000,
        )
        / 10000
    )
    print(f"GlobalConfig (default values):     {time_default * 1000:.3f}ms")

    # Test 2: GlobalConfig with custom nested configs
    time_custom = (
        timeit.timeit(
            """GlobalConfig(
            transcription=TranscriptionConfig(model_name="gemini-2.5-flash"),
            extraction=ExtractionConfig(default_provider="claude")
        )""",
            setup="from inkwell.config.schema import GlobalConfig, TranscriptionConfig, ExtractionConfig",
            number=10000,
        )
        / 10000
    )
    print(f"GlobalConfig (custom nested):      {time_custom * 1000:.3f}ms")

    # Test 3: TranscriptionConfig alone
    time_trans = (
        timeit.timeit(
            'TranscriptionConfig(model_name="gemini-2.5-flash")',
            setup="from inkwell.config.schema import TranscriptionConfig",
            number=10000,
        )
        / 10000
    )
    print(f"TranscriptionConfig (alone):       {time_trans * 1000:.3f}ms")

    # Test 4: ExtractionConfig alone
    time_extract = (
        timeit.timeit(
            "ExtractionConfig()",
            setup="from inkwell.config.schema import ExtractionConfig",
            number=10000,
        )
        / 10000
    )
    print(f"ExtractionConfig (alone):          {time_extract * 1000:.3f}ms")

    # Test 5: InterviewConfig alone
    time_interview = (
        timeit.timeit(
            "InterviewConfig()",
            setup="from inkwell.config.schema import InterviewConfig",
            number=10000,
        )
        / 10000
    )
    print(f"InterviewConfig (alone):           {time_interview * 1000:.3f}ms")

    # Test 6: Validation error path
    time_error = (
        timeit.timeit(
            """try:
            TranscriptionConfig(cost_threshold_usd=-1.0)
        except:
            pass""",
            setup="from inkwell.config.schema import TranscriptionConfig",
            number=10000,
        )
        / 10000
    )
    print(f"TranscriptionConfig (error path):  {time_error * 1000:.3f}ms")

    print()
    print("✅ Target: All validations should be < 1ms")
    if time_default < 0.001 and time_custom < 0.001:
        print("✅ PASS: Config validation is within acceptable limits")
    else:
        print("❌ FAIL: Config validation exceeds 1ms threshold")

    print()


def benchmark_precedence_resolution():
    """Benchmark parameter precedence resolution."""
    print("=" * 70)
    print("Precedence Resolution Performance")
    print("=" * 70)

    # Test 1: Config value wins (best case - first check succeeds)
    time_config = (
        timeit.timeit(
            'resolve_config_value("config", "param", "default")',
            setup="from inkwell.config.precedence import resolve_config_value",
            number=1_000_000,
        )
        / 1_000_000
    )
    print(f"Precedence (config wins):          {time_config * 1_000_000:.1f}ns")

    # Test 2: Param value wins (middle case - second check succeeds)
    time_param = (
        timeit.timeit(
            'resolve_config_value(None, "param", "default")',
            setup="from inkwell.config.precedence import resolve_config_value",
            number=1_000_000,
        )
        / 1_000_000
    )
    print(f"Precedence (param wins):           {time_param * 1_000_000:.1f}ns")

    # Test 3: Default value (worst case - both checks fail)
    time_default = (
        timeit.timeit(
            'resolve_config_value(None, None, "default")',
            setup="from inkwell.config.precedence import resolve_config_value",
            number=1_000_000,
        )
        / 1_000_000
    )
    print(f"Precedence (default wins):         {time_default * 1_000_000:.1f}ns")

    # Test 4: Falsy values (0, False, "") should still win
    time_zero = (
        timeit.timeit(
            "resolve_config_value(0, 5, 10)",
            setup="from inkwell.config.precedence import resolve_config_value",
            number=1_000_000,
        )
        / 1_000_000
    )
    print(f"Precedence (zero wins):            {time_zero * 1_000_000:.1f}ns")

    time_false = (
        timeit.timeit(
            "resolve_config_value(False, True, True)",
            setup="from inkwell.config.precedence import resolve_config_value",
            number=1_000_000,
        )
        / 1_000_000
    )
    print(f"Precedence (False wins):           {time_false * 1_000_000:.1f}ns")

    time_empty = (
        timeit.timeit(
            'resolve_config_value("", "param", "default")',
            setup="from inkwell.config.precedence import resolve_config_value",
            number=1_000_000,
        )
        / 1_000_000
    )
    print(f"Precedence (empty string wins):    {time_empty * 1_000_000:.1f}ns")

    print()
    avg_time = (time_config + time_param + time_default) / 3
    print(f"Average precedence resolution:     {avg_time * 1_000_000:.1f}ns")
    print()
    print("✅ Target: All resolutions should be < 1μs (1000ns)")
    if avg_time < 0.000001:
        print("✅ PASS: Precedence resolution is optimal (sub-microsecond)")
    else:
        print("❌ FAIL: Precedence resolution exceeds 1μs threshold")

    print()


def benchmark_service_instantiation():
    """Benchmark service class instantiation."""
    print("=" * 70)
    print("Service Instantiation Performance")
    print("=" * 70)

    import warnings

    warnings.filterwarnings("ignore", category=DeprecationWarning)

    # Test 1: TranscriptionManager with config (new pattern)
    time_tm_config = (
        timeit.timeit(
            "TranscriptionManager(config=TranscriptionConfig())",
            setup="from inkwell.transcription.manager import TranscriptionManager; from inkwell.config.schema import TranscriptionConfig",
            number=100,
        )
        / 100
    )
    print(f"TranscriptionManager (config):     {time_tm_config * 1000:.3f}ms")

    # Test 2: TranscriptionManager with params (deprecated pattern)
    time_tm_params = (
        timeit.timeit(
            'TranscriptionManager(model_name="gemini-2.5-flash")',
            setup="from inkwell.transcription.manager import TranscriptionManager; import warnings; warnings.filterwarnings('ignore')",
            number=100,
        )
        / 100
    )
    print(f"TranscriptionManager (params):     {time_tm_params * 1000:.3f}ms")

    # Test 3: ExtractionEngine with config (new pattern)
    time_ee_config = (
        timeit.timeit(
            "ExtractionEngine(config=ExtractionConfig())",
            setup="from inkwell.extraction.engine import ExtractionEngine; from inkwell.config.schema import ExtractionConfig",
            number=100,
        )
        / 100
    )
    print(f"ExtractionEngine (config):         {time_ee_config * 1000:.3f}ms")

    # Test 4: ExtractionEngine with params (deprecated pattern)
    time_ee_params = (
        timeit.timeit(
            'ExtractionEngine(default_provider="gemini")',
            setup="from inkwell.extraction.engine import ExtractionEngine; import warnings; warnings.filterwarnings('ignore')",
            number=100,
        )
        / 100
    )
    print(f"ExtractionEngine (params):         {time_ee_params * 1000:.3f}ms")

    print()
    overhead_tm = ((time_tm_config - time_tm_params) / time_tm_params) * 100
    overhead_ee = ((time_ee_config - time_ee_params) / time_ee_params) * 100
    print(f"TranscriptionManager overhead:     {overhead_tm:+.1f}%")
    print(f"ExtractionEngine overhead:         {overhead_ee:+.1f}%")
    print()
    print("✅ Target: Overhead should be < 10%")
    if abs(overhead_tm) < 10 and abs(overhead_ee) < 10:
        print("✅ PASS: Service instantiation overhead is acceptable")
    else:
        print("⚠️  WARNING: Service instantiation overhead exceeds 10%")

    print()


def benchmark_memory_usage():
    """Benchmark memory usage of config objects."""
    print("=" * 70)
    print("Memory Usage Analysis")
    print("=" * 70)

    import sys

    def get_deep_size(obj, seen=None):
        """Recursively calculate object size."""
        size = sys.getsizeof(obj)
        if seen is None:
            seen = set()
        obj_id = id(obj)
        if obj_id in seen:
            return 0
        seen.add(obj_id)
        if isinstance(obj, dict):
            size += sum([get_deep_size(v, seen) for v in obj.values()])
            size += sum([get_deep_size(k, seen) for k in obj.keys()])
        elif hasattr(obj, "__dict__"):
            size += get_deep_size(obj.__dict__, seen)
        elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, bytearray)):
            try:
                size += sum([get_deep_size(i, seen) for i in obj])
            except TypeError:
                pass
        return size

    # Measure individual configs
    tc = TranscriptionConfig()
    ec = ExtractionConfig()
    ic = InterviewConfig()
    gc = GlobalConfig()

    tc_size = get_deep_size(tc)
    ec_size = get_deep_size(ec)
    ic_size = get_deep_size(ic)
    gc_size = get_deep_size(gc)

    print(f"TranscriptionConfig:               {tc_size} bytes")
    print(f"ExtractionConfig:                  {ec_size} bytes")
    print(f"InterviewConfig:                   {ic_size} bytes")
    print(f"GlobalConfig (total):              {gc_size} bytes")
    print()

    # Compare with simple dict equivalent
    simple_dict = {
        "model_name": "gemini-2.5-flash",
        "api_key": None,
        "cost_threshold_usd": 1.0,
        "youtube_check": True,
    }
    dict_size = get_deep_size(simple_dict)
    print(f"Equivalent dict (TranscriptionConfig): {dict_size} bytes")
    print(
        f"Overhead:                          {tc_size - dict_size} bytes ({((tc_size - dict_size) / dict_size * 100):.1f}%)"
    )
    print()

    # Application-level context
    print("Application Context:")
    print("  Typical app memory:              ~1GB (1,073,741,824 bytes)")
    print(f"  Config overhead:                 {gc_size} bytes")
    print(f"  Percentage of total:             {(gc_size / 1073741824 * 100):.6f}%")
    print()

    print("✅ Target: Total config memory should be < 10KB")
    if gc_size < 10240:
        print("✅ PASS: Memory overhead is negligible")
    else:
        print("⚠️  WARNING: Memory overhead exceeds 10KB")

    print()


def benchmark_migration_path():
    """Benchmark backward compatibility migration."""
    print("=" * 70)
    print("Backward Compatibility Migration Performance")
    print("=" * 70)

    # Test 1: No migration (new pattern)
    time_no_migration = (
        timeit.timeit(
            """GlobalConfig(
            transcription=TranscriptionConfig(model_name="gemini-2.5-flash")
        )""",
            setup="from inkwell.config.schema import GlobalConfig, TranscriptionConfig",
            number=10000,
        )
        / 10000
    )
    print(f"No migration (new pattern):        {time_no_migration * 1000:.3f}ms")

    # Test 2: With migration (deprecated fields)
    time_with_migration = (
        timeit.timeit(
            'GlobalConfig(transcription_model="gemini-1.5-flash")',
            setup="from inkwell.config.schema import GlobalConfig",
            number=10000,
        )
        / 10000
    )
    print(f"With migration (deprecated):       {time_with_migration * 1000:.3f}ms")

    # Test 3: Migration with conflict (both old and new)
    time_conflict = (
        timeit.timeit(
            """GlobalConfig(
            transcription_model="gemini-1.5-flash",
            transcription=TranscriptionConfig(model_name="gemini-2.5-flash")
        )""",
            setup="from inkwell.config.schema import GlobalConfig, TranscriptionConfig",
            number=10000,
        )
        / 10000
    )
    print(f"Migration conflict resolution:     {time_conflict * 1000:.3f}ms")

    print()
    overhead = time_with_migration - time_no_migration
    print(
        f"Migration overhead:                {overhead * 1000:.3f}ms ({(overhead / time_no_migration * 100):.1f}%)"
    )
    print()
    print("✅ Target: Migration overhead should be < 0.1ms")
    if overhead < 0.0001:
        print("✅ PASS: Migration overhead is negligible")
    else:
        print("⚠️  INFO: Migration adds measurable overhead (expected)")

    print()


def main():
    """Run all performance benchmarks."""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "PR #20 Performance Benchmark Suite" + " " * 23 + "║")
    print("║" + " " * 15 + "Dependency Injection Pattern" + " " * 24 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    benchmark_config_validation()
    benchmark_precedence_resolution()
    benchmark_service_instantiation()
    benchmark_memory_usage()
    benchmark_migration_path()

    print("=" * 70)
    print("Benchmark Complete")
    print("=" * 70)
    print()
    print("See docs/analysis/pr20-performance-analysis.md for detailed analysis")
    print()


if __name__ == "__main__":
    main()
