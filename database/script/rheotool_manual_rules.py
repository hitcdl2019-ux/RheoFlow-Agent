import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List

def tokenize(text: str) -> str:
    text = text.replace("_", " ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return text.lower()


def infer_topic(title: str, content: str) -> str:
    haystack = f"{title}\n{content}".lower()
    if "rheotestfoam" in haystack or "rheotestfoamparameters" in haystack or "gammaepsilondotl" in haystack:
        return "rheotestfoam_config"
    if "rheointerfoam" in haystack or "vof" in haystack or "alpha1" in haystack or "p_rgh" in haystack:
        return "rheointerfoam_two_phase_config"
    if "surface tension" in haystack or "sigma" in haystack or "setfields" in haystack:
        return "rheointerfoam_two_phase_config"
    dictionary_terms = [
        "constitutiveproperties",
        "passivescalarproperties",
        "fvsolution",
        "fvschemes",
        "petscdict",
        "rheotestfoamparameters",
        "filmproperties",
    ]
    if any(term in haystack for term in dictionary_terms):
        return "configuration_dictionary"
    if "solver" in haystack or "petsc" in haystack or "hypre" in haystack or "eigen" in haystack:
        return "solver_algorithm_library"
    if "functionobject" in haystack or "gaussdef" in haystack or "scheme" in haystack:
        return "schemes_function_objects"
    if "thermo" in haystack or "temperature" in haystack or "heat" in haystack:
        return "thermo_rheology_library"
    if "constitutive" in haystack or "oldroyd" in haystack or "fene" in haystack:
        return "constitutive_model_library"
    return "rheotool_manual"


def infer_dictionary(content: str) -> str:
    names = [
        "constitutiveProperties",
        "passiveScalarProperties",
        "fvSolution",
        "fvSchemes",
        "petscDict",
        "filmProperties",
        "rheoTestFoamParameters",
        "controlDict",
    ]
    hits = [name for name in names if name.lower() in content.lower()]
    return ",".join(hits)


def infer_solver(content: str) -> str:
    names = [
        "rheoFoam",
        "rheoTestFoam",
        "rheoInterFoam",
        "rheoEFoam",
        "rheoHeatFoam",
        "rheoMultiRegionFoam",
        "rheoFilmFoam",
        "rheoBDFoam",
    ]
    hits = [name for name in names if name.lower() in content.lower()]
    return ",".join(hits)


def clean_lines(lines: Iterable[str]) -> List[str]:
    cleaned = []
    for line in lines:
        line = line.rstrip()
        if line.startswith("=====") and "PAGE" in line:
            continue
        cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.splitlines()


def section_candidates(lines: List[str], start_marker: str, end_marker: str, min_line: int = 0) -> List[Dict[str, str]]:
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if i < min_line:
            continue
        if start is None and line.strip() == start_marker:
            start = i
        elif start is not None and line.strip() == end_marker:
            end = i
            break

    if start is None:
        return []

    body = lines[start:end]
    sections = []
    current = {"section": "chapter", "title": start_marker, "lines": []}

    i = 0
    heading_re = re.compile(r"^(4\.\d+(?:\.\d+)?|5\.[1-8](?:\.\d+)?)$")
    while i < len(body):
        line = body[i].strip()
        if heading_re.match(line):
            if current["lines"]:
                sections.append(current)
            title_lines = []
            j = i + 1
            while j < len(body) and len(title_lines) < 2:
                candidate = body[j].strip()
                if candidate and not heading_re.match(candidate):
                    title_lines.append(candidate)
                if candidate and heading_re.match(candidate):
                    break
                j += 1
            current = {"section": line, "title": " ".join(title_lines), "lines": [body[i]]}
        else:
            current["lines"].append(body[i])
        i += 1

    if current["lines"]:
        sections.append(current)
    return sections


def split_long_section(section: Dict[str, str], max_chars: int = 6000, overlap: int = 500) -> List[Dict[str, str]]:
    content = "\n".join(section["lines"]).strip()
    if len(content) <= max_chars:
        return [{**section, "content": content, "part": 1}]

    chunks = []
    start = 0
    part = 1
    while start < len(content):
        end = min(len(content), start + max_chars)
        if end < len(content):
            split_at = content.rfind("\n\n", start, end)
            if split_at > start + max_chars // 2:
                end = split_at
        chunks.append({**section, "content": content[start:end].strip(), "part": part})
        if end >= len(content):
            break
        start = max(0, end - overlap)
        part += 1
    return chunks


def extract_rules(text_path: Path) -> List[Dict[str, str]]:
    raw = text_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    lines = clean_lines(raw)

    sections = []
    sections.extend(section_candidates(lines, "Chapter 4", "Chapter 5", min_line=2000))
    chapter5_ranges = [
        ("5.1", "5.2"),
        ("5.2", "5.3"),
        ("5.3", "5.4"),
        ("5.4", "5.5"),
        ("5.5", "5.6"),
        ("5.6", "5.7"),
        ("5.7", "5.8"),
        ("5.8", "Chapter 6"),
    ]
    for start_marker, end_marker in chapter5_ranges:
        sections.extend(section_candidates(lines, start_marker, end_marker, min_line=9000))

    records = []
    seen = set()
    for section in sections:
        for chunk in split_long_section(section):
            content = chunk["content"]
            if len(content.strip()) < 200:
                continue
            key = (chunk["section"], chunk["part"], content[:80])
            if key in seen:
                continue
            seen.add(key)
            title = chunk["title"] or chunk["section"]
            records.append({
                "source_type": "manual",
                "manual": "RheoTool_user_guide6.0",
                "section": chunk["section"],
                "title": title,
                "part": chunk["part"],
                "topic": infer_topic(title, content),
                "solver": infer_solver(content),
                "dictionary": infer_dictionary(content),
                "content": content,
            })
    return records


def write_jsonl(records: List[Dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> List[Dict[str, str]]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


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


def build_faiss(records: List[Dict[str, str]], database_path: Path, provider: str, model: str) -> Path:
    from langchain_core.documents import Document
    from langchain_community.vectorstores import FAISS

    documents = []
    for record in records:
        index_text = "\n".join([
            f"section: {record['section']}",
            f"title: {record['title']}",
            f"topic: {record['topic']}",
            f"solver: {record['solver']}",
            f"dictionary: {record['dictionary']}",
            record["content"][:3000],
        ])
        documents.append(Document(
            page_content=tokenize(index_text),
            metadata=record,
        ))

    vectordb = FAISS.from_documents(documents, make_embeddings(provider, model))
    model_dir_name = model.replace("/", "_").replace(":", "_")
    persist_directory = database_path / "faiss" / model_dir_name / "rheotool_manual_rules"
    vectordb.save_local(str(persist_directory))
    return persist_directory


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and index RheoTool manual rules.")
    parser.add_argument("--manual_text", default="/data/chendl/workspace/RheoTool_user_guide6_text.txt")
    parser.add_argument("--database_path", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--jsonl", default="")
    parser.add_argument("--extract_only", action="store_true")
    parser.add_argument("--embedding_provider", default=os.getenv("FOAMAGENT_EMBEDDING_PROVIDER", "huggingface"))
    parser.add_argument("--embedding_model", default=os.getenv("FOAMAGENT_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"))
    args = parser.parse_args()

    database_path = Path(args.database_path)
    jsonl_path = Path(args.jsonl) if args.jsonl else database_path / "raw" / "rheotool_manual_rules.jsonl"

    records = extract_rules(Path(args.manual_text))
    write_jsonl(records, jsonl_path)
    print(f"Wrote {len(records)} RheoTool manual rule chunks to {jsonl_path}")

    if args.extract_only:
        return

    records = load_jsonl(jsonl_path)
    out = build_faiss(records, database_path, args.embedding_provider, args.embedding_model)
    print(f"Indexed {len(records)} RheoTool manual rule chunks at {out}")


if __name__ == "__main__":
    main()
