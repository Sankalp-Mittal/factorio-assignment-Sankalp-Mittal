## Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Go To Main Directory
```bash
cd part2_assignment
```

## Install Required Libraries
```bash
pip install -r requirements.txt
```

## Run Sample Tests
```bash
python3 run_samples.py
```
This runs pytest internally

## Run Pytest for each part
```bash
pytest -q tests/test_belts.py
pytest -q tests/test_factory.py
```
Does the tests for belts and factory part respectively

## Run Factory Steady State
```bash
python3 factory/main.py < input.json > output.json
```

## Run Belt Max Flow
```bash
python3 belt/main.py < input.json > output.json
```
