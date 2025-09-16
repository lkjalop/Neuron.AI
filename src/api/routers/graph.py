from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Header
from typing import List, Dict, Any
import math
import random

try:  # primary import path when 'graph' is a top-level package
    from graph.relationships import get_graph  # type: ignore
    from graph.unify import ingest_exposure_snapshot  # type: ignore
    from graph.features import refresh_features, get_features, get_feature_metadata  # type: ignore
    from graph.embeddings import train_embeddings, get_embedding, get_embedding_meta  # type: ignore
    from graph.anomaly import score_anomalies  # type: ignore
except Exception:  # fallback to src.graph.* when project uses src layout during tests
    from src.graph.relationships import get_graph  # type: ignore
    from src.graph.unify import ingest_exposure_snapshot  # type: ignore
    from src.graph.features import refresh_features, get_features, get_feature_metadata  # type: ignore
    from src.graph.embeddings import train_embeddings, get_embedding, get_embedding_meta  # type: ignore
    from src.graph.anomaly import score_anomalies  # type: ignore

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


def _auth_guard(api_key: str | None):
    import os
    required = os.environ.get("GRAPH_API_KEY")
    if required and api_key != required:
        raise HTTPException(401, detail="invalid or missing graph api key")


@router.get("/snapshot")
def snapshot(include_features: bool = True, graph_api_key: str | None = Header(default=None, alias="X-Graph-Key")):
    _auth_guard(graph_api_key)
    g = get_graph()
    export = g.export()
    if include_features:
        export["features_meta"] = get_feature_metadata()
        export["features"] = get_features()
    return export


@router.post("/refresh-features")
def manual_refresh(graph_api_key: str | None = Header(default=None, alias="X-Graph-Key")):
    _auth_guard(graph_api_key)
    feats = refresh_features()
    return {"refreshed": True, "node_count": len(feats)}


@router.post("/ingest-exposure")
async def ingest_exposure(snapshot: Dict[str, Any], graph_api_key: str | None = Header(default=None, alias="X-Graph-Key")):
    _auth_guard(graph_api_key)
    if not isinstance(snapshot, dict):
        raise HTTPException(400, detail="snapshot must be a JSON object")
    await ingest_exposure_snapshot(snapshot)
    # refresh features after ingestion
    refresh_features()
    return {"ingested": True, "edge_count": len(get_graph().export()["edges"]) }


def _jaccard_score(node_a: str, node_b: str, neighbor_map: Dict[str, set[str]]) -> float:
    a = neighbor_map.get(node_a, set())
    b = neighbor_map.get(node_b, set())
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    union = len(a | b)
    return inter / union if union else 0.0


def _preferential_attachment(node_a: str, node_b: str, neighbor_map: Dict[str, set[str]]) -> float:
    return float(len(neighbor_map.get(node_a, [])) * len(neighbor_map.get(node_b, [])))


@router.get("/link-predict")
def link_predict(
    node_id: str = Query(..., description="Source node for which to predict potential links"),
    k: int = 5,
    heuristic: str = Query("jaccard", regex="^(jaccard|pa)$"),
    edge_type: str | None = None,
    negatives: int = Query(0, ge=0, le=100, description="Number of random non-edge negatives to return for evaluation"),
    graph_api_key: str | None = Header(default=None, alias="X-Graph-Key"),
):
    _auth_guard(graph_api_key)
    g = get_graph()
    nodes = g.nodes()
    if node_id not in nodes:
        raise HTTPException(404, detail="node not found")
    # Build neighbor map (outgoing only for now)
    neighbor_map: Dict[str, set[str]] = {}
    for n in nodes:
        neighbor_map[n] = set(g.neighbors(n, rel_type=edge_type)) if edge_type else set(g.neighbors(n))
    existing = neighbor_map.get(node_id, set())
    candidates = [n for n in nodes if n != node_id and n not in existing]
    scores = []
    for c in candidates:
        if heuristic == "jaccard":
            sc = _jaccard_score(node_id, c, neighbor_map)
        else:
            sc = _preferential_attachment(node_id, c, neighbor_map)
        if sc > 0:
            scores.append((c, sc))
    scores.sort(key=lambda x: x[1], reverse=True)
    top = scores[:k]
    result = {
        "node": node_id,
        "heuristic": heuristic,
        "edge_type_filter": edge_type,
        "predictions": [{"target": t, "score": float(s)} for t, s in top],
        "candidate_space": len(candidates),
    }
    if negatives > 0:
        # Sample negatives distinct from existing + predicted
        predicted_targets = {t for t, _ in top}
        non_edges_pool = [c for c in candidates if c not in predicted_targets]
        random.shuffle(non_edges_pool)
        picked = non_edges_pool[:negatives]
        result["negatives"] = picked
    return result

__all__ = ["router"]

@router.post("/train-embeddings")
def train(dim: int = 32, walks_per_node: int = 4, walk_length: int = 8, epochs: int = 2, seed: int | None = None, graph_api_key: str | None = Header(default=None, alias="X-Graph-Key")):
    _auth_guard(graph_api_key)
    embs = train_embeddings(dim=dim, walks_per_node=walks_per_node, walk_length=walk_length, epochs=epochs, seed=seed)
    return {"trained": True, "nodes": len(embs), "meta": get_embedding_meta()}


@router.get("/embedding/{node_id}")
def embedding(node_id: str, graph_api_key: str | None = Header(default=None, alias="X-Graph-Key")):
    _auth_guard(graph_api_key)
    vec = get_embedding(node_id)
    if vec is None:
        raise HTTPException(404, detail="embedding not found")
    return {"node": node_id, "embedding": vec, "meta": get_embedding_meta()}


@router.get("/anomalies")
def anomalies(top_k: int = 20, graph_api_key: str | None = Header(default=None, alias="X-Graph-Key")):
    _auth_guard(graph_api_key)
    return score_anomalies(top_k=top_k)
