# Automated Cost Efficiency and Performance Analytics Tool

A Python-based modular analytics tool that automatically computes operational expenditures, models cost efficiency, and visualizes performance metrics from raw variable inputs.

---

## Overview

This tool was built to answer a core business question:

"Given a set of operational variables, what is the most cost-efficient configuration, and where are the biggest areas of waste?"

It integrates multi-model data processing with automated visualization to support faster, data-driven decision-making on resource allocation.

---

## Features

- **Automated Cost Calculation** - dedicated economics.py engine computes projected operational expenditure from raw inputs
- **Performance Modeling** - physics.py models variable interactions to pinpoint optimal operating configurations
- **Data Visualization** - auto-generates charts tracking key efficiency metrics over time
- **Risk Detection** - flags operational anomalies before they escalate into costly failures

---

## Tech Stack

| Tool | Usage |
|------|-------|
| Python | Core logic and OOP architecture |
| NumPy | Numerical computation |
| Matplotlib | Performance visualization |
| OOP Design | Modular, maintainable codebase |

---

## Project Structure

```
Solids_Control_Simulator/
    main.py          Entry point and simulation runner
    economics.py     Cost calculation engine
    physics.py       Variable interaction modeling
    equipment.py     Equipment parameter definitions
    requirements.txt Dependencies
```

---

## Getting Started

```bash
git clone https://github.com/AntonioAt/Solids_Control_Simulator
pip install -r requirements.txt
python main.py
```

---

## Key Outputs

The tool generates performance curves and cost projection charts that identify:

- Optimal operating points minimizing resource consumption
- Efficiency drop-off thresholds
- Projected cost savings under different configurations

---

## Author

Laodi Antonius Sijabat
[LinkedIn](https://www.linkedin.com/in/laodi-sijabat-027b75179) | [GitHub](https://github.com/AntonioAt)
