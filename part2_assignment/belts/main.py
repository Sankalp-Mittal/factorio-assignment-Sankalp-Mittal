from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
import sys
import json

# --------------------------
# Top-level helper functions
# --------------------------

def base_name(nm: str) -> str:
    """Coalesce split names v__in / v__out back to v."""
    if nm.endswith("__in"):
        return nm[:-4]
    if nm.endswith("__out"):
        return nm[:-5]
    return nm

def edge_sort_key(E: "EdgeSpec"):
    """Deterministic sort key for edges."""
    return (E.u, E.v, E.name or "")

# ==========================
# Small Dinic implementation
# ==========================

@dataclass
class _Edge:
    to: int
    rev: int
    cap: float

class Dinic:
    def __init__(self, n: int, eps: float = 1e-9):
        self.n = n
        self.g: List[List[_Edge]] = [[] for _ in range(n)]
        self.level = [0]*n
        self.it = [0]*n
        self.EPS = eps

    def add_edge(self, fr: int, to: int, cap: float):
        assert cap >= -self.EPS, "Negative capacity not allowed"
        fwd = _Edge(to=to, rev=len(self.g[to]), cap=max(0.0, cap))
        rev = _Edge(to=fr, rev=len(self.g[fr]), cap=0.0)
        self.g[fr].append(fwd)
        self.g[to].append(rev)
        return (fr, len(self.g[fr])-1)

    def _bfs(self, s: int, t: int) -> bool:
        from collections import deque
        self.level = [-1]*self.n
        q = deque()
        self.level[s] = 0
        q.append(s)
        while q:
            v = q.popleft()
            for e in self.g[v]:
                if e.cap > self.EPS and self.level[e.to] < 0:
                    self.level[e.to] = self.level[v] + 1
                    q.append(e.to)
        return self.level[t] >= 0

    def _dfs(self, v: int, t: int, f: float) -> float:
        if v == t:
            return f
        itv = self.it[v]
        for i in range(itv, len(self.g[v])):
            self.it[v] = i
            e = self.g[v][i]
            if e.cap > self.EPS and self.level[v] < self.level[e.to]:
                d = self._dfs(e.to, t, min(f, e.cap))
                if d > self.EPS:
                    e.cap -= d
                    self.g[e.to][e.rev].cap += d
                    return d
        return 0.0

    def max_flow(self, s: int, t: int) -> float:
        flow = 0.0
        INF = 1e100
        while self._bfs(s, t):
            self.it = [0]*self.n
            while True:
                f = self._dfs(s, t, INF)
                if f <= self.EPS:
                    break
                flow += f
        return flow

    def flow_used(self, fr: int, idx: int) -> float:
        fwd = self.g[fr][idx]
        rev = self.g[fwd.to][fwd.rev]
        return rev.cap  # reverse capacity equals flow pushed

    def residual_reachable_from(self, s: int) -> Set[int]:
        seen = set()
        from collections import deque
        q = deque([s])
        seen.add(s)
        while q:
            v = q.popleft()
            for e in self.g[v]:
                if e.cap > self.EPS and e.to not in seen:
                    seen.add(e.to)
                    q.append(e.to)
        return seen


# ==========================
# Problem structures
# ==========================

@dataclass
class EdgeSpec:
    u: str
    v: str
    lo: float
    hi: float
    name: Optional[str] = None  # optional label

@dataclass
class Problem:
    nodes: Set[str]
    edges: List[EdgeSpec]
    node_caps: Dict[str, float]
    sources: Dict[str, float]   # must contain exactly one entry
    sink: str
    eps: float

# ==========================
# Input parsing (isolated)
# ==========================

def parse_input_json(data: dict) -> Problem:
    """
    Assumed fields:
      edges: [{from,to,lo,hi}]
      node_caps: {node: cap}
      sources: {single_source_name: supply}  # exactly one entry
      sink: "sinkname"
      nodes: [...]  # optional
      tolerance: float  # optional
    """
    eps = float(data.get("tolerance", 1e-9))
    edges = []
    for i, e in enumerate(data.get("edges", [])):
        edges.append(EdgeSpec(
            u=str(e["from"]),
            v=str(e["to"]),
            lo=float(e["lo"]),
            hi=float(e["hi"]),
            name=e.get("name") or f"e{i}"
        ))
    node_caps = {str(k): float(v) for k, v in data.get("node_caps", {}).items()}
    sources = {str(k): float(v) for k, v in data.get("sources", {}).items()}
    sink = str(data["sink"])

    nodes = set()
    nodes.update(data.get("nodes", []))
    for e in edges:
        nodes.add(e.u); nodes.add(e.v)
    nodes.update(sources.keys())
    nodes.add(sink)

    # Ignore caps on source/sink (per spec)
    for s in list(sources.keys()) + [sink]:
        if s in node_caps:
            node_caps.pop(s, None)

    return Problem(nodes=nodes, edges=edges, node_caps=node_caps,
                   sources=sources, sink=sink, eps=eps)

# ==========================
# Solver
# ==========================

class LowerBoundFlowSolver:
    def __init__(self, prob: Problem):
        self.P = prob
        self.EPS = prob.eps

        self.split_in: Dict[str, str] = {}
        self.split_out: Dict[str, str] = {}

        self.forward_handles: List[Tuple[int, int, str]] = []  # (fr_id, idx, tag)
        self.edge_map: List[Dict] = []  # metadata for each transformed original edge

    def _all_graph_nodes(self) -> List[str]:
        names = set(self.P.nodes)
        for v in self.P.node_caps.keys():
            names.add(f"{v}__in")
            names.add(f"{v}__out")
        return sorted(names)

    def _to_final_name(self, x: str, as_src: bool) -> str:
        if x in self.P.node_caps:
            return f"{x}__out" if as_src else f"{x}__in"
        return x

    def _cap_arc_name(self, v: str) -> Tuple[str, str]:
        return (f"{v}__in", f"{v}__out")

    def build_transformed(self):
        # --- Node id mapping
        base_nodes = self._all_graph_nodes()
        self.name2id = {name: i for i, name in enumerate(base_nodes)}
        self.id2name = {i: name for name, i in self.name2id.items()}

        # --- Flow graph with SS/TT
        self.flow = Dinic(n=len(base_nodes) + 2, eps=self.EPS)
        self.SS = len(base_nodes)
        self.TT = len(base_nodes) + 1
        self.id2name[self.SS] = "SS"
        self.id2name[self.TT] = "TT"

        # --- Node-cap arcs (v_in -> v_out)
        self.cap_arc_handle: Dict[str, Tuple[int, int]] = {}
        for v, cap in sorted(self.P.node_caps.items()):
            vin, vout = self._cap_arc_name(v)
            fr = self.name2id[vin]; to = self.name2id[vout]
            h = self.flow.add_edge(fr, to, cap)
            self.cap_arc_handle[v] = h

        # --- Balances due to lower bounds (including circulation trick)
        self.balance: Dict[int, float] = {i: 0.0 for i in range(len(base_nodes))}
        self.edge_map = []
        self.forward_handles = []

        # Original edges: add (hi-lo) and do balances: b[u]-=lo, b[v]+=lo
        for e in sorted(self.P.edges, key=edge_sort_key):
            u_final = self._to_final_name(e.u, as_src=True)
            v_final = self._to_final_name(e.v, as_src=False)
            u_id = self.name2id[u_final]
            v_id = self.name2id[v_final]

            lo = e.lo
            hi = e.hi
            assert hi + self.EPS >= lo, f"Edge {e.name} has hi < lo"

            cap = max(0.0, hi - lo)
            h = self.flow.add_edge(u_id, v_id, cap)
            self.forward_handles.append((h[0], h[1], "original"))
            self.edge_map.append({
                "orig_u": e.u,
                "orig_v": e.v,
                "u_final": u_id,
                "v_final": v_id,
                "lo": lo,
                "hi": hi,
                "name": e.name,
                "handle": h
            })

            self.balance[u_id] -= lo
            self.balance[v_id] += lo

        # --- Single source + circulation trick (add implicit edge sink->source with [S,S] via balances)
        assert len(self.P.sources) == 1, "This solver expects exactly one source."
        (src_name, S_total), = self.P.sources.items()
        src_id = self.name2id[self._to_final_name(src_name, as_src=True)]
        sink_id = self.name2id[self._to_final_name(self.P.sink, as_src=False)]

        # Equivalent to adding an edge sink->source with lo=hi=S_total (cap = 0), only affects balances:
        # b[sink] -= S, b[source] += S
        self.balance[sink_id] -= S_total
        self.balance[src_id]  += S_total

        # --- Hook SS/TT to satisfy balances
        self.required = 0.0
        for node_id, b in self.balance.items():
            if b > self.EPS:
                self.flow.add_edge(self.SS, node_id, b)
                self.required += b
            elif b < -self.EPS:
                self.flow.add_edge(node_id, self.TT, -b)

    def solve(self) -> dict:
        self.build_transformed()
        pushed = self.flow.max_flow(self.SS, self.TT)
        if pushed + 1e-12 >= self.required - self.EPS:
            return self._success_output()
        return self._infeasible_certificate(total=pushed)

    def _success_output(self) -> dict:
        flows_out = []
        for meta in self.edge_map:
            fr_id, idx = meta["handle"]
            used = self.flow.flow_used(fr_id, idx)
            f = meta["lo"] + used
            f = max(meta["lo"], min(meta["hi"] + self.EPS, f))
            flows_out.append({
                "from": meta["orig_u"],
                "to": meta["orig_v"],
                "flow": f
            })

        # Sum of flows into the sink (original graph)
        sink = self.P.sink
        total = 0.0
        for r in flows_out:
            if r["to"] == sink:
                total += r["flow"]

        return {
            "status": "ok",
            "max_flow_per_min": total,
            "flows": flows_out
        }

    def _infeasible_certificate(self, total: float) -> dict:
        R = self.flow.residual_reachable_from(self.SS)

        # Nodes on the source side of min-cut (coalesced)
        cut_nodes = set()
        for vid in R:
            nm = self.id2name.get(vid, "")
            if nm in ("SS", "TT"):
                continue
            cut_nodes.add(base_name(nm))

        # Tight edges crossing the cut (reachable -> unreachable) that are saturated
        tight_edges = []
        seen_pairs = set()
        for meta in self.edge_map:
            u = meta["u_final"]; v = meta["v_final"]
            u_in_R = (u in R); v_in_R = (v in R)
            if u_in_R and not v_in_R:
                fr_id, idx = meta["handle"]
                residual = self.flow.g[fr_id][idx].cap
                if residual <= self.EPS:
                    key = (meta["orig_u"], meta["orig_v"])
                    if key not in seen_pairs:
                        seen_pairs.add(key)
                        tight_edges.append({
                            "from": meta["orig_u"],
                            "to": meta["orig_v"],
                            "flow_needed": 0
                        })

        # Tight node caps crossing the cut and saturated
        tight_nodes = []
        for v, h in self.cap_arc_handle.items():
            fr_id, idx = h
            u = fr_id
            w = self.flow.g[fr_id][idx].to
            u_in_R = (u in R); w_in_R = (w in R)
            residual = self.flow.g[fr_id][idx].cap
            if u_in_R and not w_in_R and residual <= self.EPS:
                tight_nodes.append(v)

        deficit = max(0.0, self.required - total)
        k = len(tight_edges)
        if k >= 1 and deficit > self.EPS:
            share = deficit / k
            for e in tight_edges:
                e["flow_needed"] = share


        return {
            "status": "infeasible",
            "cut_reachable": sorted(cut_nodes),
            "deficit": {
                "demand_balance": deficit,
                "tight_nodes": sorted(tight_nodes),
                "tight_edges": tight_edges
            }
        }

# ==========================
# Public API
# ==========================

def solve_lower_bounded_flow(input_json: dict) -> dict:
    prob = parse_input_json(input_json)
    solver = LowerBoundFlowSolver(prob)
    return solver.solve()

# ==========================
# CLI
# ==========================

def _read_stdin_json():
    raw = sys.stdin.read()
    return json.loads(raw)

def _write_stdout_json(obj):
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False))

def main():
    data = _read_stdin_json()
    out = solve_lower_bounded_flow(data)
    _write_stdout_json(out)

if __name__ == "__main__":
    main()
