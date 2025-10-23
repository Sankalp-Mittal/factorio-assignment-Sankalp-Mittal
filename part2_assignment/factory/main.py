import json, math, sys
from typing import Dict, List, Tuple
import numpy as np

EPS = 1e-9

def read_stdin_json():
    data = sys.stdin.read()
    return json.loads(data)

def pick_recipes_dict(input_data: dict) -> Dict:
    # Accept both "recipes" and the misspelled "recipies"
    if "recipes" in input_data:
        return input_data["recipes"]
    if "recipies" in input_data:
        return input_data["recipies"]
    raise ValueError('Missing "recipes"/"recipies" in input')

def compute_machine_effects(machines: Dict, modules: Dict) -> Tuple[Dict[str, float], Dict[str, float]]:
    # craft_speed[m]: base crafts_per_min scaled by speed (unitless factor).
    # prod_mult[m]: 1 + prod (multiplies outputs only).
    craft_speed = {}
    prod_mult = {}
    for mname, props in machines.items():
        init_crafts = float(props["crafts_per_min"])
        speed_boost = float(modules.get(mname, {}).get("speed", 0.0))
        prod_boost = float(modules.get(mname, {}).get("prod", 0.0))
        craft_speed[mname] = init_crafts * (1.0 + speed_boost)
        prod_mult[mname] = 1.0 + prod_boost
    return craft_speed, prod_mult

def eff_crafts_per_min_for_recipe(recipe: Dict, craft_speed: Dict[str, float]) -> float:
    m = recipe["machine"]
    time_s = float(recipe["time_s"])
    # Spec formula: eff_crafts/min = machine_crafts_per_min * 60/time_s
    # (the machine_crafts_per_min already includes speed multiplier)
    return craft_speed[m] * 60.0 / time_s

def items_from_recipes(recipes: Dict, raw_caps: Dict, target_item: str) -> List[str]:
    items = set()
    for r in recipes.values():
        for k in r.get("in", {}).keys():
            items.add(k)
        for k in r.get("out", {}).keys():
            items.add(k)
    for k in raw_caps.keys():
        items.add(k)
    items.add(target_item)
    return sorted(items)

def build_recipe_order(recipes: Dict) -> List[str]:
    return sorted(recipes.keys())

def build_item_index(items: List[str]) -> Dict[str, int]:
    return {name: idx for idx, name in enumerate(items)}

def build_stoich_matrix(recipes: Dict,
                        recipe_names: List[str],
                        items: List[str],
                        item_index: Dict[str, int],
                        prod_mult: Dict[str, float]) -> np.ndarray:
    I = len(items)
    R = len(recipe_names)
    S = np.zeros((I, R), dtype=float)
    for j, rname in enumerate(recipe_names):
        r = recipes[rname]
        m = r["machine"]
        pm = float(prod_mult[m])
        for i_name, v in r.get("in", {}).items():
            S[item_index[i_name], j] -= float(v)
        for i_name, v in r.get("out", {}).items():
            S[item_index[i_name], j] += float(v) * pm  # productivity multiplies outputs only
    return S

def split_items(items: List[str],
                raw_caps: Dict[str, float],
                target_item: str) -> Tuple[List[str], List[str], List[str]]:
    raws = [i for i in items if i in raw_caps]
    others = [i for i in items if i not in raw_caps]
    if target_item not in items:
        raise ValueError("Target item not present in items universe")
    intermediates = [i for i in others if i != target_item]
    return raws, intermediates, [target_item]

def has_target_producer(recipes: Dict, target_item: str) -> bool:
    for r in recipes.values():
        if target_item in r.get("out", {}):
            return True
    return False

def assemble_equalities(S: np.ndarray,
                        items: List[str],
                        item_index: Dict[str, int],
                        raws: List[str],
                        intermediates: List[str],
                        target_item: str,
                        target_rate: float) -> Tuple[np.ndarray, np.ndarray, Dict[str, int]]:
    """
    Build Aeq * y = beq, with y = [x (R vars); u_raw (|raws| vars)].
    For intermediates: S_i * x = 0
    For target:        S_t * x = target_rate
    For raws:          S_i * x + u_i = 0
    """
    Irows = []
    grows = []  # row RHS
    # intermediates
    for i_name in intermediates:
        i = item_index[i_name]
        Irows.append((i, "intermediate"))
        grows.append(0.0)
    # target
    t = item_index[target_item]
    Irows.append((t, "target"))
    grows.append(float(target_rate))
    # raws
    for i_name in raws:
        i = item_index[i_name]
        Irows.append((i, "raw"))
        grows.append(0.0)

    beq = np.array(grows, dtype=float)
    num_rows = len(Irows)
    R = S.shape[1]
    U = len(raws)
    Aeq = np.zeros((num_rows, R + U), dtype=float)

    # Fill recipe part
    for row_idx, (i, kind) in enumerate(Irows):
        Aeq[row_idx, :R] = S[i, :]
    # Fill raw-draw columns (identity on raw rows)
    raw_col_index = {raws[k]: k for k in range(U)}
    for row_idx, (i, kind) in enumerate(Irows):
        if kind == "raw":
            raw_name = items[i]
            col = R + raw_col_index[raw_name]
            Aeq[row_idx, col] = 1.0

    return Aeq, beq, raw_col_index

def solve_nonnegative_equalities(Aeq: np.ndarray,
                                 beq: np.ndarray,
                                 R: int,
                                 U: int,
                                 max_iters: int = 20,
                                 tol: float = 1e-9) -> Tuple[np.ndarray, bool]:
    """
    Very small active-set-like refinement:
    1) Start with unconstrained least-squares.
    2) Project negatives to zero.
    3) Re-solve on the positive set a few times.
    Returns y = [x(0..R-1), u(R..R+U-1)], and success flag
    """
    # Initial LS
    try:
        y = np.linalg.lstsq(Aeq, beq, rcond=None)[0]
    except np.linalg.LinAlgError:
        return np.zeros(R + U), False

    y = np.maximum(0.0, y)

    for _ in range(max_iters):
        active = y > 0
        if not np.any(active):
            # Try full LS again (not expected often)
            try:
                y_new = np.linalg.lstsq(Aeq, beq, rcond=None)[0]
            except np.linalg.LinAlgError:
                return y, False
            y_new = np.maximum(0.0, y_new)
            if np.linalg.norm(y_new - y, ord=np.inf) < 1e-12:
                break
            y = y_new
            continue

        # Solve exactly for active set (inactive vars fixed to 0)
        A_act = Aeq[:, active]
        try:
            y_act, *_ = np.linalg.lstsq(A_act, beq, rcond=None)
        except np.linalg.LinAlgError:
            return y, False

        y_new = np.zeros_like(y)
        y_new[active] = y_act
        y_new = np.maximum(0.0, y_new)

        # Check residual
        r = Aeq @ y_new - beq
        if np.linalg.norm(r, ord=np.inf) <= tol:
            return y_new, True

        # Keep improving
        if np.linalg.norm(y_new - y, ord=np.inf) < 1e-12:
            # Stuck; exit loop and check residual outside
            y = y_new
            break
        y = y_new

    # Final residual check
    r = Aeq @ y - beq
    ok = np.linalg.norm(r, ord=np.inf) <= tol
    return y, ok

def compute_machine_usage(recipes: Dict,
                          recipe_names: List[str],
                          x: np.ndarray,
                          craft_speed: Dict[str, float]) -> Dict[str, float]:
    per_machine_usage = {}
    for mname in craft_speed.keys():
        per_machine_usage[mname] = 0.0
    for j, rname in enumerate(recipe_names):
        r = recipes[rname]
        m = r["machine"]
        eff = eff_crafts_per_min_for_recipe(r, craft_speed)
        if eff <= EPS:
            return {}  # invalid recipe speed; will be caught as infeasible
        per_machine_usage[m] += x[j] / eff
    return per_machine_usage

def ceil_machines(per_machine_usage: Dict[str, float]) -> Dict[str, int]:
    return {m: int(math.ceil(v - 1e-12)) for m, v in per_machine_usage.items()}  # tiny epsilon to avoid 1.00000000001

def compute_raw_consumption(raws: List[str],
                            raw_col_index: Dict[str, int],
                            x_and_u: np.ndarray,
                            R: int) -> Dict[str, float]:
    # u_i is the draw from raw supply. That's exactly the "raw consumption per min".
    ans = {}
    for raw_name, col in raw_col_index.items():
        ans[raw_name] = float(max(0.0, x_and_u[R + col]))
    return ans

def check_caps_integer_machines(machine_counts: Dict[str, int], max_machines: Dict[str, int]) -> List[str]:
    problems = []
    for m, used in machine_counts.items():
        cap = int(max_machines.get(m, 0))
        if used > cap + 0:
            problems.append(f"{m} cap")
    return problems

def check_raw_caps(raw_consumption: Dict[str, float], raw_caps: Dict[str, float]) -> List[str]:
    problems = []
    for item, used in raw_consumption.items():
        cap = float(raw_caps.get(item, 0.0))
        if used > cap + 1e-9:
            problems.append(f"{item} supply")
    return problems

def per_recipe_dict(recipe_names: List[str], x: np.ndarray) -> Dict[str, float]:
    return {r: float(x[j]) for j, r in enumerate(recipe_names)}

def per_machine_counts_dict(machine_counts: Dict[str, int]) -> Dict[str, int]:
    return dict(machine_counts)

def per_recipe_effective_outputs_per_min(recipes, recipe_names, x, prod_mult):
    # Sum of all outputs (with productivity) per recipe, items/min
    out = {}
    for j, rname in enumerate(recipe_names):
        r = recipes[rname]
        pm = float(prod_mult[r["machine"]])
        total = 0.0
        for item, qty in r.get("out", {}).items():
            total += float(qty) * pm * float(x[j])
        out[rname] = total
    return out

def per_item_outputs_per_min(recipes, recipe_names, x, prod_mult):
    # Aggregated per-item production (with productivity), items/min
    acc = {}
    for j, rname in enumerate(recipe_names):
        r = recipes[rname]
        pm = float(prod_mult[r["machine"]])
        for item, qty in r.get("out", {}).items():
            acc[item] = acc.get(item, 0.0) + float(qty) * pm * float(x[j])
    return acc


def process_input(input_data: any):
    machines = input_data["machines"]
    recipes = pick_recipes_dict(input_data)
    modules = input_data.get("modules", {})
    limits = input_data["limits"]
    target = input_data["target"]

    target_item = target.get("item", None)
    if not target_item:
        raise ValueError("No target item given")

    target_rate = float(target["rate_per_min"])

    raw_caps = {k: float(v) for k, v in limits.get("raw_supply_per_min", {}).items()}
    max_machines_json = limits.get("max_machines", {})
    max_machines = {k: int(max_machines_json.get(k, 0)) for k in machines.keys()}

    craft_speed, prod_mult = compute_machine_effects(machines, modules)
    return target_item, target_rate, recipes, craft_speed, prod_mult, max_machines, raw_caps

def make_infeasible_output(hints: List[str]) -> dict:
    # Hints should be unique and stable
    ordered = []
    seen = set()
    for h in hints:
        if h not in seen:
            seen.add(h)
            ordered.append(h)
    return {
        "status": "infeasible",
        "bottleneck_hint": ordered
    }


def make_success_output(per_recipe: Dict[str, float], 
                        per_machine_counts: Dict[str, int], 
                        raw_consumption: Dict[str, float],
                        per_recipe_outputs=None, per_item_outputs=None) -> dict:
    out = {
        "status": "ok",
        "per_recipe_crafts_per_min": per_recipe,
        "per_machine_counts": per_machine_counts,
        "raw_consumption_per_min": raw_consumption
    }
    if per_recipe_outputs is not None:
        out["per_recipe_effective_outputs_per_min"] = per_recipe_outputs
    if per_item_outputs is not None:
        out["per_item_outputs_per_min"] = per_item_outputs
    return out


def check_feasibility(target_item: str,
                      target_rate_per_min: float,
                      recipes: Dict,
                      raw_supply_max_per_min: Dict[str, float],
                      machine_crafts_per_min: Dict[str, float],
                      machine_output_multiplier: Dict[str, float],
                      max_machines: Dict[str, int]) -> dict:
    # Guard: need at least one producer for target
    if not has_target_producer(recipes, target_item):
        return make_infeasible_output(["no recipe produces target item"])

    # Universe
    items = items_from_recipes(recipes, raw_supply_max_per_min, target_item)
    recipe_names = build_recipe_order(recipes)
    item_index = build_item_index(items)

    # Build S (with productivity on outputs)
    # (We reuse machine_output_multiplier through prod_mult input here)
    prod_mult = machine_output_multiplier
    S = build_stoich_matrix(recipes, recipe_names, items, item_index, prod_mult)

    # Split into raws / intermediates / target
    raws, intermediates, _target_list = split_items(items, raw_supply_max_per_min, target_item)

    # Equalities: Aeq * [x; u] = beq
    Aeq, beq, raw_col_index = assemble_equalities(
        S=S,
        items=items,
        item_index=item_index,
        raws=raws,
        intermediates=intermediates,
        target_item=target_item,
        target_rate=target_rate_per_min
    )
    R = len(recipe_names)
    U = len(raws)

    # Solve for a nonnegative steady-state
    y, ok = solve_nonnegative_equalities(Aeq, beq, R, U, max_iters=30, tol=1e-9)
    if not ok:
        return make_infeasible_output(["steady-state balance infeasible"])

    x = y[:R]
    u = y[R:]

    # Ensure raws are net-consumed only (no net production of raw items)
    # Recall equality was: S_raw * x + u_raw = 0  => S_raw * x = -u_raw <= 0
    raw_prod_violation = []
    for idx, raw_name in enumerate(raws):
        i = item_index[raw_name]
        net = float(S[i, :] @ x)  # should be <= 0 (consumption)
        if net > 1e-9:
            raw_prod_violation.append(raw_name)
    if raw_prod_violation:
        hints = [f"{rn} must be net-consumed" for rn in raw_prod_violation]
        return make_infeasible_output(hints)

    # Check raw caps
    raw_consumption = compute_raw_consumption(raws, raw_col_index, y, R)
    raw_cap_hints = check_raw_caps(raw_consumption, raw_supply_max_per_min)
    if raw_cap_hints:
        return make_infeasible_output(raw_cap_hints)

    # Machine usage and integer rounding
    per_machine_usage = compute_machine_usage(recipes, recipe_names, x, machine_crafts_per_min)
    if not per_machine_usage:
        return make_infeasible_output(["invalid machine/recipe speed"])
    per_machine_counts_int = ceil_machines(per_machine_usage)
    mach_hints = check_caps_integer_machines(per_machine_counts_int, max_machines)
    if mach_hints:
        return make_infeasible_output(mach_hints)

    # Success: format outputs
    per_recipe = per_recipe_dict(recipe_names, x)
    per_machine_counts = per_machine_counts_dict(per_machine_counts_int)
    per_recipe_outputs = per_recipe_effective_outputs_per_min(recipes, recipe_names, x, machine_output_multiplier)
    per_item_outputs = per_item_outputs_per_min(recipes, recipe_names, x, machine_output_multiplier)

    return make_success_output(
        per_recipe=per_recipe,
        per_machine_counts=per_machine_counts,
        raw_consumption=raw_consumption
    )

def main():
    input_data = read_stdin_json()
    target_item, target_rate_per_min, recipes, craft_speed, prod_mult, max_machines, raw_caps = process_input(input_data)

    # For clarity: machine_crafts_per_min holds speed-adjusted base (no time_s), prod_mult holds (1+prod)
    # The feasibility routine expects these two dicts.
    result = check_feasibility(
        target_item=target_item,
        target_rate_per_min=target_rate_per_min,
        recipes=recipes,
        raw_supply_max_per_min=raw_caps,
        machine_crafts_per_min=craft_speed,
        machine_output_multiplier=prod_mult,
        max_machines=max_machines
    )
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
