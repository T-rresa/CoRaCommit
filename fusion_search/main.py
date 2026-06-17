import argparse

from project_paths import ARTIFACTS_DIR, INDEX_DIR, RAW_DATA_DIR


def build_index(args):
    if args.type == "codebert":
        from embedding.codebert_build_index import DEVICE, build_codebert_index

        output = args.output or INDEX_DIR / "codebert_diff_index.pkl"
        build_codebert_index(args.input, output, args.model, args.batch_size, args.device or DEVICE)
        return

    if args.type == "jina":
        from embedding.jina_build_diff_index import build_jina_index

        output = args.output or INDEX_DIR / "jina_diff_index.pkl"
        build_jina_index(args.input, output, args.model, args.batch_size, args.max_seq_length)
        return

    raise ValueError(f"Unsupported index type: {args.type}")


def export_backend(args):
    from export_backend_resources import export_backend_resources

    export_backend_resources(
        output_dir=args.output_dir,
        models=args.models,
        codebert_index=args.codebert_index,
        jina_index=args.jina_index,
        id_field=args.id_field,
        keep_empty_diff=args.keep_empty_diff,
        fail_on_invalid=args.fail_on_invalid,
    )


def build_parser():
    parser = argparse.ArgumentParser(description="Unified entry point for FusionSearch.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build-index", help="Build a dense embedding index.")
    build_parser.add_argument("type", choices=["codebert", "jina"])
    build_parser.add_argument("--input", default=RAW_DATA_DIR / "apachecm" / "full.jsonl")
    build_parser.add_argument("--output", default=None)
    build_parser.add_argument("--model", default=None)
    build_parser.add_argument("--batch-size", type=int, default=None)
    build_parser.add_argument("--device", default=None)
    build_parser.add_argument("--max-seq-length", type=int, default=4096)
    build_parser.set_defaults(func=build_index)

    export_parser = subparsers.add_parser(
        "export-backend",
        help="Export dense pkl indexes into backend RESOURCE_PATH format.",
    )
    export_parser.add_argument("--output-dir", default=ARTIFACTS_DIR / "backend_resource")
    export_parser.add_argument(
        "--models",
        nargs="+",
        default=["codebert", "jina"],
        choices=["codebert", "jina"],
    )
    export_parser.add_argument("--codebert-index", default=INDEX_DIR / "codebert_diff_index.pkl")
    export_parser.add_argument("--jina-index", default=INDEX_DIR / "jina_diff_index.pkl")
    export_parser.add_argument(
        "--id-field",
        default="row",
        help="raw_items field to use as backend doc id. Default 'row' uses the source row number; use e.g. commit_sha for commit ids.",
    )
    export_parser.add_argument(
        "--keep-empty-diff",
        action="store_true",
        help="Keep rows whose diff is empty. By default they are skipped.",
    )
    export_parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Fail instead of skipping rows with NaN/Inf/zero vectors or empty diff.",
    )
    export_parser.set_defaults(func=export_backend)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "build-index":
        if args.type == "codebert":
            args.model = args.model or "microsoft/codebert-base"
            args.batch_size = args.batch_size or 8
        elif args.type == "jina":
            args.model = args.model or "jinaai/jina-embeddings-v2-base-code"
            args.batch_size = args.batch_size or 2

    args.func(args)


if __name__ == "__main__":
    main()
