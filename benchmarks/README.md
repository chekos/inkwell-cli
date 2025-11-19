# Performance Benchmarks

This directory contains performance benchmark scripts for measuring the runtime characteristics of the Inkwell CLI.

## Available Benchmarks

### config_performance.py

Comprehensive performance benchmark for PR #20's dependency injection implementation.

**Measures:**
- Config validation overhead (Pydantic validation)
- Precedence resolution performance (resolve_config_value)
- Service instantiation overhead (TranscriptionManager, ExtractionEngine)
- Memory usage of config objects
- Backward compatibility migration performance

**Usage:**
```bash
# Run all benchmarks
python benchmarks/config_performance.py

# Or with uv
uv run benchmarks/config_performance.py
```

**Expected Output:**
```
╔════════════════════════════════════════════════════════════════════╗
║          PR #20 Performance Benchmark Suite                       ║
║               Dependency Injection Pattern                        ║
╚════════════════════════════════════════════════════════════════════╝

======================================================================
Config Validation Performance
======================================================================
GlobalConfig (default values):     0.523ms
GlobalConfig (custom nested):      0.687ms
TranscriptionConfig (alone):       0.156ms
ExtractionConfig (alone):          0.089ms
InterviewConfig (alone):           0.234ms
TranscriptionConfig (error path):  0.245ms

✅ Target: All validations should be < 1ms
✅ PASS: Config validation is within acceptable limits

======================================================================
Precedence Resolution Performance
======================================================================
Precedence (config wins):          32.5ns
Precedence (param wins):           45.8ns
Precedence (default wins):         48.2ns
Precedence (zero wins):            31.2ns
Precedence (False wins):           30.8ns
Precedence (empty string wins):    33.1ns

Average precedence resolution:     42.2ns

✅ Target: All resolutions should be < 1μs (1000ns)
✅ PASS: Precedence resolution is optimal (sub-microsecond)

...
```

**Pass Criteria:**
- Config validation: < 1ms per object
- Precedence resolution: < 1μs (1000ns) per call
- Service instantiation overhead: < 10% vs baseline
- Memory overhead: < 10KB per GlobalConfig
- Migration overhead: < 0.1ms

## Running Benchmarks

### Prerequisites

```bash
# Install project dependencies
uv sync --dev
```

### Run Individual Benchmarks

```bash
# Config performance (PR #20)
python benchmarks/config_performance.py
```

### Run All Benchmarks

```bash
# Run all benchmark scripts
for script in benchmarks/*.py; do
    echo "Running $script..."
    python "$script"
    echo
done
```

### Profiling

For detailed profiling, use cProfile:

```bash
# Profile config validation
python -m cProfile -s cumtime benchmarks/config_performance.py > profile.txt

# Or use line_profiler for line-by-line analysis
kernprof -l -v benchmarks/config_performance.py
```

## Benchmark Best Practices

1. **Run multiple times:** Performance can vary, run benchmarks 3-5 times and average
2. **Close other apps:** Minimize background processes for accurate measurements
3. **Use consistent environment:** Same Python version, same machine
4. **Baseline comparison:** Record results before and after changes
5. **Statistical significance:** Use large iteration counts (10k-1M) for micro-benchmarks

## Performance Targets

Based on PR #20 analysis (see `docs/analysis/pr20-performance-analysis.md`):

| Metric | Target | Measured | Status |
|--------|--------|----------|--------|
| Config validation | < 1ms | 0.5-0.8ms | ✅ Pass |
| Precedence resolution | < 1μs | 30-50ns | ✅ Pass |
| Service init overhead | < 10% | 3-5% | ✅ Pass |
| Memory overhead | < 10KB | ~1.2KB | ✅ Pass |
| Migration overhead | < 0.1ms | 0.02-0.05ms | ✅ Pass |

## Adding New Benchmarks

To add a new benchmark:

1. Create a new Python file in `benchmarks/`
2. Use `timeit` module for accurate timing
3. Include clear pass/fail criteria
4. Document expected results
5. Follow the format of existing benchmarks

Example:

```python
#!/usr/bin/env python3
"""Benchmark description."""

import timeit

def benchmark_feature():
    """Benchmark specific feature."""
    time = timeit.timeit(
        'feature_call()',
        setup='from module import feature_call',
        number=10000
    ) / 10000

    print(f"Feature time: {time * 1000:.3f}ms")

    # Pass/fail criteria
    assert time < 0.001, f"Too slow: {time * 1000:.3f}ms"
    print("✅ PASS")

if __name__ == '__main__':
    benchmark_feature()
```

## References

- **Full Performance Analysis:** `docs/analysis/pr20-performance-analysis.md`
- **Performance Summary:** `pr20-performance-summary.md`
- **Python timeit docs:** https://docs.python.org/3/library/timeit.html
- **Profiling guide:** https://docs.python.org/3/library/profile.html
