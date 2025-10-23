# Factory Steady State

A tiny, deterministic command-line tool that checks **feasibility** of a Factorio-style factory at **steady state**, including **cycles** and **byproducts**. It reads one JSON from stdin and prints one JSON to stdout.

* Enforces exact target production.
* Balances all intermediates (including cyclic ones).
* Draws raws only within their caps.
* Respects integer **machine counts** against per-type caps.
* Applies **speed** and **productivity** modules correctly.
* Deterministic outputs given identical inputs.

---
## 1) CLI

```bash
python factory/main.py < input.json > output.json
```

* No extra prints/logs. Only JSON on stdout.
* Finishes quickly on typical laptop hardware.

---

## 2) Input schema

```json
{
  "machines": {
    "assembler_1": {"crafts_per_min": 30},
    "chemical": {"crafts_per_min": 60}
  },
  "recipes": {
    "iron_plate": {
      "machine": "chemical",
      "time_s": 3.2,
      "in": {"iron_ore": 1},
      "out": {"iron_plate": 1}
    },
    "copper_plate": {
      "machine": "chemical",
      "time_s": 3.2,
      "in": {"copper_ore": 1},
      "out": {"copper_plate": 1}
    },
    "green_circuit": {
      "machine": "assembler_1",
      "time_s": 0.5,
      "in": {"iron_plate": 1, "copper_plate": 3},
      "out": {"green_circuit": 1}
    }
  },
  "modules": {
    "assembler_1": {"prod": 0.1, "speed": 0.15},
    "chemical": {"prod": 0.2, "speed": 0.1}
  },
  "limits": {
    "raw_supply_per_min": {"iron_ore": 5000, "copper_ore": 5000},
    "max_machines": {"assembler_1": 300, "chemical": 300}
  },
  "target": {"item": "green_circuit", "rate_per_min": 1800}
}
```

Notes

* Key `"recipes"` or legacy `"recipies"` are both accepted.
* `modules` is optional; missing fields default to 0.
* `machines[*].crafts_per_min` is the **base per-minute craft rate** for that machine type (before modules).
* Recipe `time_s` is the **per-craft time**.

---

## 3) Output schema

### Success

```json
{
  "per_machine_counts": {
    "assembler_1": 1,
    "chemical": 5
  },
  "per_recipe_crafts_per_min": {
    "copper_plate": 4090.909090909089,
    "green_circuit": 1636.3636363636356,
    "iron_plate": 1363.6363636363658
  },
  "raw_consumption_per_min": {
    "copper_ore": 4090.90909090909,
    "iron_ore": 1363.636363636364
  },
  "status": "ok"
}
```

Fields

* `per_recipe_crafts_per_min` — **crafts/min** (x_r). This is **not** productivity-adjusted.
* `per_recipe_effective_outputs_per_min` — sum of outputs per recipe (items/min), **with productivity**.
* `per_item_outputs_per_min` — aggregated items/min per item across all recipes, **with productivity**.
* `per_machine_counts` — **integer** machines by type (see §6 for counting policy).
* `raw_consumption_per_min` — actual raw draw (u_i) (items/min).

### Infeasible

```json
{
  "status": "infeasible",
  "bottleneck_hint": [
    "no recipe produces target item",
    "steady-state balance infeasible",
    "iron_ore supply",
    "assembler_1 cap"
  ]
}
```

`bottleneck_hint` contains deterministic, human-readable reasons.

---

## 4) Physics & math (how it works)

We build a **stoichiometric matrix** $(S \in \mathbb{R}^{|I|\times|R|})$:

$$
S_{i,r} = \underbrace{\text{out}*{i,r}\cdot (1+\text{prod}*{m(r)})}*{\text{outputs with productivity}} - \underbrace{\text{in}*{i,r}}_{\text{inputs}}.
$$

Variables:

* $(x_r \ge 0)$: crafts/min for recipe (r).
* $(u_i \ge 0)$: raw draw (items/min) for raw items (i) that have caps.

Steady-state equalities:

* Target item (t): $(Sx)_t = \text{target\_rate}$.
* Intermediates (non-raw, non-target): $((Sx)_i = 0)$.
* Raws: $((Sx)_i + u_i = 0)$  ⇒ raws are **net-consumed only**.

Caps checked after solving:

* $(0 \le u_i \le \text{raw\_cap}_i)$.
* Integer machine counts must not exceed `max_machines`.

**Effective recipe speed** (per recipe (r) on machine (m)):

$$
\text{eff\_crafts\_per\_min}(r) = \underbrace{\text{machines}[m].\text{crafts\_per\_min}\cdot(1+\text{speed}*m)}*{\text{speed-adjusted machine rate}} \cdot \frac{60}{\text{time\_s}(r)}.
$$

**Cycles are handled automatically:** the equalities apply to **all** items at once; no DAG or topological order is required. Cyclic items are in the “intermediate” set, so they must balance to zero net accumulation.

Numerics:

* We solve $(A_{\rm eq},[x;u] = b_{\rm eq})$ with a small **projected least-squares** routine enforcing $(x,u \ge 0)$.
* Tolerance: $(|\text{residual}|_{\infty} \le 1e{-9})$.

---

## 5) Module semantics

* **Speed**: multiplies the machine’s base `crafts_per_min` as ((1+\text{speed})). Speed affects **eff_crafts_per_min** via the formula above.
* **Productivity**: multiplies **outputs only**; inputs are unchanged.

---

## 6) Machine counting policy (important)

Two reasonable policies exist:

1. **Time-sharing across recipes (default in the simple version)**

   * Compute continuous usage per type: (\sum_r x_r/\text{eff}(r)), then **ceil once per machine type**.
   * Produces lower counts (machines can be shared between recipes).

2. **No time-sharing (dedicated lines) — recommended for strict integer layouts**

   * For each recipe: machines(_r) = (\lceil x_r/\text{eff}(r)\rceil).
   * Then **sum integers** per machine type.
   * Produces higher counts (each recipe gets whole machines).

> If you want (2), switch to the provided `compute_machine_counts_per_recipe(...)` in code and pass `eff_fn` (see comments in the code). Caps are checked on the resulting integer counts.

---

## 7) Tolerances

* Balance tolerance: `1e-9` (absolute).
* Raw caps & machine caps: checked with small epsilons.
* Ties are broken deterministically by sorted recipe/item/machine names.
* You may enable a small rounding pass before printing to make 1799.999999 show as 1800.0 (helpers included in comments).

---

## 8) Example

Given the sample input above and the spec speed formula, you might see:

```json
{
  "status": "ok",
  "per_recipe_crafts_per_min": {
    "green_circuit": 1636.363636,
    "iron_plate": 1363.636364,
    "copper_plate": 4090.909091
  },
  "per_machine_counts": {
    "assembler_1": 1,
    "chemical": 5
  },
  "raw_consumption_per_min": {
    "iron_ore": 1363.636364,
    "copper_ore": 4090.909091
  }
}
```

* Crafts/min × productivity = items/min (e.g., (1636.36 \times 1.1 \approx 1800)).
* Machine counts are integers and respect caps; counts depend on the chosen policy (see §6).

---

## 9) Errors & hints

Typical `bottleneck_hint` values:

* `"no recipe produces target item"`
* `"steady-state balance infeasible"`
* `"<raw_item> supply"` (raw cap exceeded)
* `"<machine_type> cap"` (machine cap exceeded)
* `"<raw_item> must be net-consumed"` (solution tries to net-produce a raw)

---

## 10) Code map (top-level, no nested functions)

* **Parsing & prep:** `read_stdin_json`, `process_input`, `compute_machine_effects`, `items_from_recipes`
* **Math core:** `build_stoich_matrix`, `assemble_equalities`, `solve_nonnegative_equalities`
* **Accounting:** `eff_crafts_per_min_for_recipe`, `compute_machine_usage` / `compute_machine_counts_per_recipe`, `ceil_machines`
* **Caps & outputs:** `check_raw_caps`, `check_caps_integer_machines`, output builders
* **Extras:** `per_recipe_effective_outputs_per_min`, `per_item_outputs_per_min`, rounding helpers (optional)
* **Entry point:** `main()`

---

# Belt Processing Max Flow

A tiny, deterministic command-line tool that decides **feasibility** of a conveyor/belt network with **lower/upper edge bounds** and optional **node throughput caps**, assuming **one fixed source** and **one sink**. It reads one JSON from stdin and prints one JSON to stdout.

* Enforces all lower/upper bounds `lo ≤ f ≤ hi`.
* Honors node throughput caps (via node-splitting).
* Supports cycles and arbitrary topology.
* Emits a **valid flow** if feasible; else a **clear certificate** (cut, tight edges/nodes, deficit).
* Deterministic outputs given identical inputs.

---

## 1) CLI

```bash
python belts/main.py < input.json > output.json
```

* No extra prints/logs. Only JSON on stdout.
* Fast on typical laptop hardware.

---

## 2) Input schema
Since no Input schema was given I assumed the following schema and have implemented my code accordingly

```json
{
  "nodes": ["s", "a", "b", "c", "sink"],            // optional; inferred if omitted
  "edges": [
    {"from": "s", "to": "a", "lo": 0,   "hi": 1500},
    {"from": "a", "to": "b", "lo": 0,   "hi": 800},
    {"from": "b", "to": "sink", "lo": 200, "hi": 800},
    {"from": "a", "to": "c", "lo": 0,   "hi": 500},
    {"from": "c", "to": "sink", "lo": 0,   "hi": 500}
  ],
  "node_caps": { "a": 1500, "b": 800, "c": 500 },   // optional; ignored for source/sink
  "sources": { "s": 1500 },                         // exactly one entry
  "sink": "sink",
  "tolerance": 1e-9                                  // optional; default 1e-9
}
```

**Notes**

* Graph is directed. Multiple edges allowed if you list them separately.
* `lo, hi` are per-edge per-minute bounds. Require `hi ≥ lo ≥ 0`.
* `node_caps[v]` limits total **throughput** at `v` (handled by node-splitting).
* Caps on the single source and the sink are ignored.

---

## 3) Output schema

### ✅ Success

```json
{
  "status": "ok",
  "max_flow_per_min": 1500.0,
  "flows": [
    {"from": "s", "to": "a", "flow": 1500.0},
    {"from": "a", "to": "b", "flow": 900.0},
    {"from": "a", "to": "c", "flow": 600.0},
    {"from": "b", "to": "sink", "flow": 900.0},
    {"from": "c", "to": "sink", "flow": 600.0}
  ]
}
```

`max_flow_per_min` equals the single source supply if feasible. `flows` lists one valid assignment satisfying all `lo/hi` and node caps.

### ❌ Infeasible

```json
{
  "status": "infeasible",
  "cut_reachable": ["a", "s"],
  "deficit": {
    "demand_balance": 200.0,
    "tight_nodes": [],
    "tight_edges": [
      {"from": "a", "to": "b", "flow_needed": 100.0},
      {"from": "a", "to": "c", "flow_needed": 100.0}
    ]
  }
}
```

Fields

* `cut_reachable`: nodes on the **source side** of the min-cut (after coalescing split nodes).
* `demand_balance`: total shortfall (how much extra capacity the cut needs).
* `tight_edges`: saturated edges crossing the cut (reachable → unreachable).
  **flow_needed** is **equally split** across all tight edges. (Could also implement splitting in ratio to current flows but chosen this option because of simplicty)
* `tight_nodes`: capped nodes whose internal `(v_in→v_out)` cap is tight across the cut.

---

## 4) Method (how it works)

**1) Node caps via splitting**
For any capped node `v` (not source/sink):

* Create `v_in` and `v_out`.
* Redirect all incoming edges to `v_in` and all outgoing from `v_out`.
* Add cap edge `v_in → v_out` with capacity `cap(v)`.

**2) Lower bounds transform**
For each edge `(u→v)` with bounds `[lo, hi]`:

* Replace it with capacity `hi − lo`.
* Update node balances:

  ```
  balance[u] -= lo
  balance[v] += lo
  ```

**3) Single source via circulation trick**
Given source `s` with supply `S` and sink `t`, conceptually require a fixed flow `S` from `t → s` (no edge added; only balances):

```
balance[s] += S
balance[t] -= S
```

**4) Feasibility check**
Create super-source `SS` and super-sink `TT`:

* If `balance[x] > 0`, add `SS → x` with capacity `balance[x]`.
* If `balance[x] < 0`, add `x → TT` with capacity `-balance[x]`.
* Run **max-flow** (`Dinic`) from `SS` to `TT`.
  If the flow saturates all `SS` edges (within tolerance), the original instance is feasible.

**5) Recover original flows**
For every original edge:

```
f = lo + flow_used_on_transformed_edge
```

(Internal cap and super edges are not reported.)

---

## 5) Determinism & tolerance

* Node/edge names are **sorted lexicographically** before ID mapping and insertion.
* Dinic traversal order is stable → deterministic results.
* All comparisons use `EPS = tolerance` (default `1e-9`).
  Edge feasibility checks accept `f ≤ hi + EPS` and conservation within `EPS`.

---

## 6) Examples

### Feasible

The example in §2 is feasible with `S = 1500` and total capacity into `sink` = `800 + 500 = 1300` **plus** `b→sink` lower bound `200` already counted, so the residual network can satisfy balances—resulting in a valid 1500 flow split as shown in §3 (Success).

### Infeasible

If the same graph’s capacities into `sink` total **only 1300** while the supply is **1500**, you get `demand_balance = 200`. The min-cut sits at `{s,a}` and the two edges `a→b`, `a→c` are saturated; **flow_needed** splits equally to `100` and `100`.

---

## 7) Errors & hints

Common reasons for infeasibility:

* Sum of capacities into the sink (after lower bounds) is too small.
* A node cap is binding on the source side of the cut (`tight_nodes` shows which).
* An edge’s `lo` already over-subscribes downstream capacity (`tight_edges` catches it).

---

## 8) Dependencies

* Python 3.9+
* No third-party libraries required.

---

## 9) Code map

* **Parsing:** `parse_input_json(data) -> Problem` (single source; easy to adapt)
* **Core types:** `EdgeSpec`, `Problem`
* **Max-flow:** `Dinic` (`add_edge`, `max_flow`, `flow_used`, `residual_reachable_from`)
* **Solver:** `LowerBoundFlowSolver`

  * `build_transformed()` — node-split, lower-bound shift, balances, SS/TT wiring
  * `solve()` — runs Dinic and returns either success or certificate
  * `_success_output()` — reconstructs original flows
  * `_infeasible_certificate()` — cut set, **equal-split** of `demand_balance` over tight edges
* **CLI:** reads stdin JSON, writes stdout JSON

---

## 10) Testing checklist

* **Bounds:** For every edge, `lo ≤ f ≤ hi + EPS`.
* **Conservation:** Net in/out at all non-super nodes is within `EPS`.
* **Caps:** If a node cap is tight and cuts the min-cut, it appears in `tight_nodes`.
* **Certificate:** In infeasible runs, `sum(flow_needed)` over `tight_edges` equals `demand_balance` (equal-split rule).

---

## 11) Adapting the input

If your upstream schema changes (e.g., fields renamed, different source specification), only touch **`parse_input_json`**. The solver operates on a canonical `Problem` and doesn’t need modification.
