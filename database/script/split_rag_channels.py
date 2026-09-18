"""Split the existing mixed FAISS assets into certified version channels.

Vectors are copied from the existing Qwen index, so this operation does not
download or recompute embeddings.
"""

import argparse
import copy
import pickle
from pathlib import Path

import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS


RHEOTOOL_SOLVERS = {
    "rheoFoam", "rheoTestFoam", "rheoInterFoam", "rheoEFoam",
    "rheoHeatFoam", "rheoFilmFoam", "rheoBDFoam", "rheoMultiRegionFoam",
}
CHANNEL_METADATA = {
    "v9-rheotool": {
        "channel": "v9-rheotool", "version": "v9",
        "distribution": "foundation+rheotool",
    },
    "v10-foundation": {
        "channel": "v10-foundation", "version": "v10",
        "distribution": "foundation",
    },
}


def document_channel(index_name, metadata):
    if index_name == "rheotool_manual_rules":
        return "v9-rheotool"
    if index_name == "openfoam_command_help":
        return "v9-rheotool" if metadata.get("command") in RHEOTOOL_SOLVERS else "v10-foundation"
    if metadata.get("case_domain") == "rheology" or metadata.get("case_solver") in RHEOTOOL_SOLVERS:
        return "v9-rheotool"
    return "v10-foundation"


def split_index(source, destinations):
    index = faiss.read_index(str(source / "index.faiss"))
    with (source / "index.pkl").open("rb") as handle:
        docstore, index_to_docstore_id = pickle.load(handle)

    selected = {channel: [] for channel in destinations}
    for position in range(index.ntotal):
        doc_id = index_to_docstore_id[position]
        doc = docstore.search(doc_id)
        channel = document_channel(source.name, doc.metadata)
        selected[channel].append((position, doc_id, doc))

    for channel, output in destinations.items():
        entries = selected[channel]
        if not entries:
            continue
        vectors = index.reconstruct_batch([position for position, _, _ in entries])
        output_index = faiss.IndexFlatL2(index.d)
        output_index.add(vectors)
        output_docs = {}
        output_mapping = {}
        for new_position, (_, doc_id, original) in enumerate(entries):
            doc = copy.deepcopy(original)
            doc.metadata.update(CHANNEL_METADATA[channel])
            output_docs[doc_id] = doc
            output_mapping[new_position] = doc_id
        output.parent.mkdir(parents=True, exist_ok=True)
        FAISS(None, output_index, InMemoryDocstore(output_docs), output_mapping).save_local(str(output))
        print(f"{channel}/{source.name}: {len(entries)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--model", default="Qwen_Qwen3-Embedding-0.6B")
    args = parser.parse_args()
    source_root = args.database / "faiss" / args.model
    if not source_root.is_dir():
        parser.error(f"source index directory not found: {source_root}")

    for source in sorted(path.parent for path in source_root.glob("*/index.faiss")):
        destinations = {
            channel: args.database / channel / "faiss" / args.model / source.name
            for channel in CHANNEL_METADATA
        }
        split_index(source, destinations)


if __name__ == "__main__":
    main()
