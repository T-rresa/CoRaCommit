# -*- coding: utf-8 -*-
import argparse
import json
import pickle
import sqlite3
from pathlib import Path

import numpy as np

from project_paths import ARTIFACTS_DIR, INDEX_DIR, resolve_project_path


DEFAULT_OUTPUT_DIR = ARTIFACTS_DIR / "backend_resource"
DEFAULT_INDEX_PATHS = {
    "codebert": INDEX_DIR / "codebert_diff_index.pkl",
    "jina": INDEX_DIR / "jina_diff_index.pkl",
}


def _load_dense_index(index_path):
    with open(index_path, "rb") as f:
        data = pickle.load(f)

    if "embeddings" not in data or "raw_items" not in data:
        raise ValueError(f"{index_path} must contain 'embeddings' and 'raw_items'")

    embeddings = np.asarray(data["embeddings"], dtype=np.float32)
    raw_items = data["raw_items"]
    if embeddings.ndim != 2:
        raise ValueError(f"{index_path} embeddings must be a 2D array")
    if len(embeddings) != len(raw_items):
        raise ValueError(
            f"{index_path} has {len(embeddings)} embeddings but {len(raw_items)} raw_items"
        )

    return embeddings, raw_items


def _doc_id(item, row_index, id_field):
    if id_field == "row":
        return str(row_index)

    value = item.get(id_field)
    if value is None or value == "":
        raise ValueError(f"Missing id field '{id_field}' at row {row_index}")
    return str(value)


def _is_non_empty_diff(item):
    return bool(str(item.get("diff", "")).strip())


def _as_doc(doc_id, item):
    return {
        "id": doc_id,
        "message": item.get("message", ""),
        "diff": item.get("diff", ""),
        "repo": item.get("repo", ""),
    }


def _write_docs_db(docs, output_dir):
    db_path = output_dir / "docs.db"
    tmp_path = output_dir / "docs.db.tmp"
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(str(tmp_path))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE docs (
                id TEXT PRIMARY KEY,
                message TEXT,
                diff TEXT,
                repo TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE VIRTUAL TABLE docs_fts USING fts5(
                id,
                diff,
                content='docs',
                content_rowid='rowid'
            )
            """
        )
        cur.execute(
            """
            CREATE TRIGGER docs_ai AFTER INSERT ON docs BEGIN
              INSERT INTO docs_fts(rowid, id, diff) VALUES (new.rowid, new.id, new.diff);
            END;
            """
        )
        cur.execute(
            """
            CREATE TRIGGER docs_ad AFTER DELETE ON docs BEGIN
              INSERT INTO docs_fts(docs_fts, rowid, id, diff)
              VALUES('delete', old.rowid, old.id, old.diff);
            END;
            """
        )
        cur.execute(
            """
            CREATE TRIGGER docs_au AFTER UPDATE ON docs BEGIN
              INSERT INTO docs_fts(docs_fts, rowid, id, diff)
              VALUES('delete', old.rowid, old.id, old.diff);
              INSERT INTO docs_fts(rowid, id, diff) VALUES (new.rowid, new.id, new.diff);
            END;
            """
        )
        cur.executemany(
            "INSERT INTO docs (id, message, diff, repo) VALUES (?, ?, ?, ?)",
            [(doc["id"], doc["message"], doc["diff"], doc["repo"]) for doc in docs],
        )
        conn.commit()
    finally:
        conn.close()

    tmp_path.replace(db_path)
    return db_path


def _write_docs_jsonl(docs, output_dir):
    path = output_dir / "docs.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return path


def _valid_embedding_mask(embeddings):
    finite = np.isfinite(embeddings).all(axis=1)
    non_zero = np.linalg.norm(embeddings, axis=1) > 0.0
    return finite & non_zero


def _write_model_resources(model_name, embeddings, raw_items, output_dir, id_field, keep_empty_diff, fail_on_invalid):
    import faiss  # type: ignore

    ids = np.array([_doc_id(item, i, id_field) for i, item in enumerate(raw_items)])
    mask = _valid_embedding_mask(embeddings)

    if not keep_empty_diff:
        non_empty = np.array([_is_non_empty_diff(item) for item in raw_items], dtype=bool)
        mask = mask & non_empty

    invalid_count = int(len(mask) - mask.sum())
    if invalid_count and fail_on_invalid:
        raise ValueError(
            f"{model_name} has {invalid_count} empty/invalid rows. "
            "Run without --fail-on-invalid to skip them."
        )

    filtered_embeddings = np.asarray(embeddings[mask], dtype=np.float32)
    filtered_ids = ids[mask]
    if filtered_embeddings.size == 0:
        raise ValueError(f"{model_name} has no valid embeddings to export")

    embeddings_dir = output_dir / "embeddings"
    faiss_dir = output_dir / "faiss"
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    faiss_dir.mkdir(parents=True, exist_ok=True)

    np.save(embeddings_dir / f"{model_name}.vecs.npy", filtered_embeddings)
    np.save(embeddings_dir / f"{model_name}.doc_ids.npy", filtered_ids)

    faiss_vectors = filtered_embeddings.copy()
    faiss.normalize_L2(faiss_vectors)
    index = faiss.IndexFlatIP(faiss_vectors.shape[1])
    index.add(faiss_vectors)
    faiss.write_index(index, str(faiss_dir / f"{model_name}.index"))

    return {
        "total": len(raw_items),
        "exported": int(mask.sum()),
        "skipped": invalid_count,
        "dim": int(filtered_embeddings.shape[1]),
    }


def _collect_docs(indexes, id_field, keep_empty_diff):
    docs_by_id = {}
    conflicts = []

    for _model_name, (_embeddings, raw_items) in indexes.items():
        for row_index, item in enumerate(raw_items):
            if not keep_empty_diff and not _is_non_empty_diff(item):
                continue

            doc_id = _doc_id(item, row_index, id_field)
            doc = _as_doc(doc_id, item)
            existing = docs_by_id.get(doc_id)
            if existing and existing != doc:
                conflicts.append(doc_id)
                continue
            docs_by_id[doc_id] = doc

    if conflicts:
        sample = ", ".join(conflicts[:5])
        raise ValueError(
            f"Conflicting documents for ids: {sample}. "
            "Use --id-field commit_sha if row ids are not shared across indexes."
        )

    return list(docs_by_id.values())


def export_backend_resources(
    output_dir=DEFAULT_OUTPUT_DIR,
    models=("codebert", "jina"),
    codebert_index=DEFAULT_INDEX_PATHS["codebert"],
    jina_index=DEFAULT_INDEX_PATHS["jina"],
    id_field="row",
    keep_empty_diff=False,
    fail_on_invalid=False,
):
    output_dir = resolve_project_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_paths = {
        "codebert": resolve_project_path(codebert_index),
        "jina": resolve_project_path(jina_index),
    }

    indexes = {}
    for model_name in models:
        index_path = index_paths[model_name]
        if not index_path.exists():
            raise FileNotFoundError(f"{model_name} index not found: {index_path}")
        print(f"[INFO] Loading {model_name} index: {index_path}")
        indexes[model_name] = _load_dense_index(index_path)

    docs = _collect_docs(indexes, id_field, keep_empty_diff)
    docs.sort(key=lambda doc: doc["id"])
    db_path = _write_docs_db(docs, output_dir)
    _write_docs_jsonl(docs, output_dir)
    print(f"[INFO] Wrote docs.db with {len(docs)} docs: {db_path}")

    for model_name, (embeddings, raw_items) in indexes.items():
        stats = _write_model_resources(
            model_name,
            embeddings,
            raw_items,
            output_dir,
            id_field,
            keep_empty_diff,
            fail_on_invalid,
        )
        print(
            f"[INFO] {model_name}: total={stats['total']} exported={stats['exported']} "
            f"skipped={stats['skipped']} dim={stats['dim']}"
        )

    print(f"[DONE] Backend resource directory: {output_dir}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Export FusionSearch dense pkl indexes into backend RESOURCE_PATH format."
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["codebert", "jina"],
        choices=["codebert", "jina"],
    )
    parser.add_argument("--codebert-index", default=DEFAULT_INDEX_PATHS["codebert"])
    parser.add_argument("--jina-index", default=DEFAULT_INDEX_PATHS["jina"])
    parser.add_argument(
        "--id-field",
        default="row",
        help="raw_items field to use as backend doc id. Default 'row' uses the source row number; use e.g. commit_sha for commit ids.",
    )
    parser.add_argument(
        "--keep-empty-diff",
        action="store_true",
        help="Keep rows whose diff is empty. By default they are skipped.",
    )
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Fail instead of skipping rows with NaN/Inf/zero vectors or empty diff.",
    )
    return parser


def main():
    args = build_parser().parse_args()
    export_backend_resources(
        output_dir=args.output_dir,
        models=args.models,
        codebert_index=args.codebert_index,
        jina_index=args.jina_index,
        id_field=args.id_field,
        keep_empty_diff=args.keep_empty_diff,
        fail_on_invalid=args.fail_on_invalid,
    )


if __name__ == "__main__":
    main()
