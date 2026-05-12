import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np


def load_non_empty_diff_ids(db_path: Path) -> set[int]:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT CAST(id AS INTEGER)
            FROM docs
            WHERE diff IS NOT NULL
              AND TRIM(diff) != ''
            """
        )
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def backup_file(path: Path, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_dir / path.name)


def rebuild_model(resource_dir: Path, model_name: str, keep_ids: set[int], do_backup: bool) -> None:
    embeddings_dir = resource_dir / "embeddings"
    faiss_dir = resource_dir / "faiss"

    vecs_path = embeddings_dir / f"{model_name}.vecs.npy"
    doc_ids_path = embeddings_dir / f"{model_name}.doc_ids.npy"
    index_path = faiss_dir / f"{model_name}.index"

    missing = [str(p) for p in [vecs_path, doc_ids_path] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required files for {model_name}: {missing}")

    doc_ids = np.load(doc_ids_path)
    mask = np.fromiter((int(doc_id) in keep_ids for doc_id in doc_ids), dtype=bool, count=len(doc_ids))
    kept_count = int(mask.sum())
    removed_count = int(len(doc_ids) - kept_count)

    if kept_count == 0:
        raise RuntimeError(f"No non-empty diff samples left for model {model_name}.")

    print(f"[{model_name}] total={len(doc_ids)} keep={kept_count} remove={removed_count}")

    vecs = np.load(vecs_path, mmap_mode="r")
    filtered_vecs = np.asarray(vecs[mask], dtype=np.float32)
    filtered_doc_ids = np.asarray(doc_ids[mask])
    # Release memmap before overwriting the original file on Windows.
    del vecs

    if do_backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = resource_dir / "backups" / f"{model_name}_{timestamp}"
        print(f"[{model_name}] backing up original files to {backup_dir}")
        backup_file(vecs_path, backup_dir)
        backup_file(doc_ids_path, backup_dir)
        if index_path.exists():
            backup_file(index_path, backup_dir)

    tmp_vecs_path = vecs_path.with_suffix(vecs_path.suffix + ".tmp")
    tmp_doc_ids_path = doc_ids_path.with_suffix(doc_ids_path.suffix + ".tmp")
    tmp_index_path = index_path.with_suffix(index_path.suffix + ".tmp")

    np.save(tmp_vecs_path, filtered_vecs)
    np.save(tmp_doc_ids_path, filtered_doc_ids)
    print(f"[{model_name}] wrote filtered vectors and doc ids")

    # Import faiss lazily so the script can still be opened/read in environments
    # where faiss is not installed.
    import faiss  # type: ignore

    dim = filtered_vecs.shape[1]
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(filtered_vecs)
    index.add(filtered_vecs)
    faiss.write_index(index, str(tmp_index_path))
    tmp_vecs_real = Path(str(tmp_vecs_path) + ".npy") if not str(tmp_vecs_path).endswith(".npy") else tmp_vecs_path
    tmp_doc_ids_real = Path(str(tmp_doc_ids_path) + ".npy") if not str(tmp_doc_ids_path).endswith(".npy") else tmp_doc_ids_path
    tmp_index_real = tmp_index_path

    tmp_vecs_real.replace(vecs_path)
    tmp_doc_ids_real.replace(doc_ids_path)
    tmp_index_real.replace(index_path)
    print(f"[{model_name}] rebuilt faiss index with {index.ntotal} vectors")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filter out empty-diff samples and rebuild FAISS indices for codebert/jina."
    )
    parser.add_argument(
        "--resource-dir",
        default="resource",
        help="Path to the resource directory containing docs.db, embeddings/, and faiss/.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["codebert", "jina"],
        choices=["codebert", "jina"],
        help="Models to rebuild.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backing up original vecs/doc_ids/index files before overwriting.",
    )
    args = parser.parse_args()

    resource_dir = Path(args.resource_dir).resolve()
    db_path = resource_dir / "docs.db"
    if not db_path.exists():
        raise FileNotFoundError(f"docs.db not found: {db_path}")

    keep_ids = load_non_empty_diff_ids(db_path)
    print(f"[global] non-empty diff ids: {len(keep_ids)}")

    for model_name in args.models:
        rebuild_model(
            resource_dir=resource_dir,
            model_name=model_name,
            keep_ids=keep_ids,
            do_backup=not args.no_backup,
        )

    print("[done] rebuild completed")


if __name__ == "__main__":
    main()
