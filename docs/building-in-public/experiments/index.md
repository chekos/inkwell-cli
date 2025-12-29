# Research & Experiments

Empirical tests, benchmarks, proof-of-concepts, and performance validations.

## Format

Use the template: [YYYY-MM-DD-template.md](./YYYY-MM-DD-template.md)

For complex experiments, create a folder:
```
YYYY-MM-DD-experiment-name/
├── README.md (following template)
├── data/
├── scripts/
└── results/
```

## When to Create an Experiment

Run experiments when:
- Comparing performance of different approaches
- Validating assumptions about libraries or frameworks
- Testing edge cases or scale limits
- Exploring new technologies before adoption

## What to Include

- **Objective** - Clear question you're answering
- **Method** - Exact setup, tools, versions
- **Results** - Data, metrics, observations
- **Conclusion** - What you learned and how it informs decisions

## Reproducibility

Always document:
- Tool versions (Node, npm, framework versions)
- Environment (OS, hardware specs if relevant)
- Commands used to run the experiment
- Where to find raw data

This allows others (or future you) to verify results.
