"""
Batch Ingestion Script
Orchestrates the end-to-end ingestion of the entire raw corpus.
Iterates through all supported files and serializes the resulting chunks.
"""

import glob
import os
import pickle

from src.ingestion.pipeline import IngestionPipeline


def main() -> None:
    """
    Main entry point for batch processing.
    Loads the pipeline, scans data/raw, and saves all TextNodes to a pickle file.
    """
    pipeline = IngestionPipeline()
    raw_dir = "data/raw"
    output_dir = "data/processed/chunks"

    os.makedirs(output_dir, exist_ok=True)

    all_files = glob.glob(os.path.join(raw_dir, "**/*.*"), recursive=True)
    valid_extensions = (".pdf", ".docx", ".xlsx")

    all_nodes = []

    for file_path in all_files:
        if file_path.lower().endswith(valid_extensions):
            try:
                nodes = pipeline.run(file_path)
                all_nodes.extend(nodes)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

    # Save all nodes for the next phase (Storage)
    output_path = os.path.join(output_dir, "ingested_nodes.pkl")
    with open(output_path, "wb") as f:
        pickle.dump(all_nodes, f)

    print(f"\nPhase 1 Complete: Total {len(all_nodes)} chunks saved to {output_path}")


if __name__ == "__main__":
    main()
