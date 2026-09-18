#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml


CASE_FILES = (
    "0/U",
    "0/p",
    "0/tau",
    "constant/constitutiveProperties",
    "constant/transportProperties",
    "constant/turbulenceProperties",
    "system/blockMeshDict",
    "system/controlDict",
    "system/fvSchemes",
    "system/fvSolution",
    "system/sampleDict",
    "Allrun",
)


def tokenize(text: str) -> str:
    text = text.replace("_", " ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return text.lower()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping YAML: {path}")
    return data


def base_metadata(bench_dir: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    target = metadata.get("target") or {}
    physics = metadata.get("physics") or {}
    source = metadata.get("source") or {}
    return {
        "source_type": "certified_benchmark",
        "benchmark_id": metadata["id"],
        "benchmark_status": metadata.get("status", "unknown"),
        "benchmark_path": str(bench_dir),
        "case_name": metadata["id"],
        "case_domain": physics.get("case_domain", "unknown"),
        "case_category": physics.get("case_category", "unknown"),
        "case_solver": target.get("solver", "unknown"),
        "solver": target.get("solver", "unknown"),
        "channel": target.get("channel", "unknown"),
        "version": target.get("version", "unknown"),
        "distribution": target.get("distribution", "unknown"),
        "constitutive_family": physics.get("constitutive_family", "unknown"),
        "model": physics.get("model", "unknown"),
        "phase_type": physics.get("phase_type", "unknown"),
        "geometry_family": physics.get("geometry_family", "unknown"),
        "flow_regime": physics.get("flow_regime", "unknown"),
        "objective": physics.get("objective", "benchmark-reproduction"),
        "source_doi": source.get("doi"),
        "source_repo": source.get("repo"),
        "source_case_path": source.get("case_path"),
    }


def make_record(content: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "page_content": tokenize("\n".join([
            str(metadata.get("benchmark_id", "")),
            str(metadata.get("title", "")),
            str(metadata.get("topic", "")),
            str(metadata.get("solver", "")),
            str(metadata.get("model", "")),
            str(metadata.get("file_path", "")),
            content[:3000],
        ])),
        "metadata": {**metadata, "full_content": content},
    }


def benchmark_records(bench_dir: Path) -> list[dict[str, Any]]:
    metadata_path = bench_dir / "metadata.yaml"
    metadata = load_yaml(metadata_path)
    base = base_metadata(bench_dir, metadata)
    records: list[dict[str, Any]] = []

    overview = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
    records.append(make_record(
        "\n".join([
            "Certified benchmark metadata",
            overview,
        ]),
        {
            **base,
            "section": "metadata",
            "topic": "benchmark_overview",
            "title": metadata.get("source", {}).get("title", metadata["id"]),
            "case_set": "metadata",
            "file_path": "metadata.yaml",
        },
    ))

    notes_path = bench_dir / "runtime_notes.md"
    if notes_path.exists():
        records.append(make_record(
            notes_path.read_text(encoding="utf-8"),
            {
                **base,
                "section": "runtime_notes",
                "topic": "runtime_constraints",
                "title": "Runtime notes and RAG usage policy",
                "case_set": "notes",
                "file_path": "runtime_notes.md",
            },
        ))

    for case_set in ("official_case", "runtime_case"):
        root = bench_dir / case_set
        if not root.exists():
            continue
        for rel in CASE_FILES:
            path = root / rel
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            records.append(make_record(
                content,
                {
                    **base,
                    "section": case_set,
                    "topic": "openfoam_case_file",
                    "title": f"{metadata['id']} {case_set} {rel}",
                    "case_set": case_set,
                    "file_path": rel,
                },
            ))
    return records


def discover_benchmarks(knowledge_path: Path) -> list[Path]:
    return sorted(
        path.parent
        for path in knowledge_path.glob("*/metadata.yaml")
        if path.parent.name != "__pycache__"
    )


def write_jsonl(records: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def sync_jsonl(knowledge_path: Path, database_path: Path) -> dict[str, Any]:
    all_records: list[dict[str, Any]] = []
    for bench_dir in discover_benchmarks(knowledge_path):
        all_records.extend(benchmark_records(bench_dir))

    by_channel: dict[str, list[dict[str, Any]]] = {}
    for record in all_records:
        channel = record["metadata"].get("channel", "unknown")
        by_channel.setdefault(channel, []).append(record)

    raw_output = database_path / "raw" / "certified_benchmarks.jsonl"
    write_jsonl(all_records, raw_output)

    channel_outputs = {}
    for channel, records in sorted(by_channel.items()):
        channel_output = database_path / channel / "raw" / "certified_benchmarks.jsonl"
        write_jsonl(records, channel_output)
        channel_outputs[channel] = str(channel_output)

    return {
        "benchmarks": len(discover_benchmarks(knowledge_path)),
        "records": len(all_records),
        "raw_output": str(raw_output),
        "channel_outputs": channel_outputs,
    }


def make_embeddings(provider: str, model: str):
    if provider == "openai":
        from langchain_openai.embeddings import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model)
    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name=model)
    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(model=model)
    raise ValueError(f"Unsupported embedding provider: {provider}")


def build_faiss(database_path: Path, provider: str, model: str) -> list[str]:
    from langchain_core.documents import Document
    from langchain_community.vectorstores import FAISS

    outputs = []
    model_dir_name = model.replace("/", "_").replace(":", "_")
    embeddings = make_embeddings(provider, model)
    for jsonl_path in sorted(database_path.glob("*/raw/certified_benchmarks.jsonl")):
        channel = jsonl_path.parent.parent.name
        documents = []
        with jsonl_path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                documents.append(Document(
                    page_content=record["page_content"],
                    metadata=record["metadata"],
                ))
        if not documents:
            continue
        vectordb = FAISS.from_documents(documents, embeddings)
        output = database_path / channel / "faiss" / model_dir_name / "certified_benchmarks"
        output.parent.mkdir(parents=True, exist_ok=True)
        vectordb.save_local(str(output))
        outputs.append(str(output))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync certified benchmark cases into RAG-ready JSONL and optional FAISS indices.")
    parser.add_argument("--knowledge-path", type=Path, default=Path("knowledge/benchmarks"))
    parser.add_argument("--database-path", type=Path, default=Path("database"))
    parser.add_argument("--build-faiss", action="store_true", help="Build channel-isolated FAISS certified_benchmarks indices.")
    parser.add_argument("--embedding-provider", default=os.getenv("FOAMAGENT_EMBEDDING_PROVIDER", "huggingface"))
    parser.add_argument("--embedding-model", default=os.getenv("FOAMAGENT_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"))
    args = parser.parse_args()

    result = sync_jsonl(args.knowledge_path, args.database_path)
    if args.build_faiss:
        result["faiss_outputs"] = build_faiss(args.database_path, args.embedding_provider, args.embedding_model)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
