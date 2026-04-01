"""
Pipeline runner — entry point for processing documents.
Handles batch execution and result logging.
"""

from pipeline.graph import build_pipeline
from pathlib import Path
from tqdm import tqdm
import json


def run_pipeline(file_paths: list, output_log: str = "pipeline_results.jsonl"):
    """Run the full pipeline on a list of file paths."""
    pipeline = build_pipeline()
    results = []

    for file_path in tqdm(file_paths, desc="Processing documents"):
        initial_state = {
            "file_path": str(file_path),
            "retry_count": 0,
            "errors": [],
            "needs_review": False,
            "is_duplicate": False,
        }
        try:
            final_state = pipeline.invoke(initial_state)
            results.append({
                "file": str(file_path),
                "status": "success",
                "doc_type": final_state.get("doc_type"),
                "write_stats": final_state.get("write_stats"),
            })
        except Exception as e:
            results.append({"file": str(file_path), "status": "error", "error": str(e)})

    with open(output_log, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    return results


if __name__ == "__main__":
    docs = list(Path("data/documents").rglob("*"))
    docs = [d for d in docs if d.is_file()]
    run_pipeline(docs)
