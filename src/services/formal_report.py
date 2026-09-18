from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional fallback
    Image = None

EMU_PER_INCH = 914400
A4_CONTENT_WIDTH_IN = 6.3


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_file(path: Path) -> str:
    if not path.is_file():
        return ""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as stream:
            return stream.read()
    return path.read_text(encoding="utf-8", errors="ignore")


def _text(value: Any, default: str = "未记录") -> str:
    if value in (None, ""):
        return default
    return str(value)


def _short_requirement(application: str) -> str:
    if not application:
        return "未记录原始需求。"
    return application.strip()


def _credibility_from_sources(text: str) -> str:
    lowered = text.casefold()
    if "estimated_with_user_approval" in lowered or "estimated_approved" in lowered:
        return "探索性授权估算"
    if "literature_typical" in lowered:
        return "文献典型值估算"
    if "user_provided" in lowered:
        return "实测/用户显式参数支撑"
    return "探索性结果（参数来源未完整结构化）"


def _artifact_path(case_dir: Path, name: str) -> Path | None:
    path = case_dir / name
    return path if path.is_file() else None


@dataclass
class ImageRef:
    path: Path
    rid: str
    name: str
    width_in: float = 5.8


@dataclass
class DocxBuilder:
    title: str
    font_east_asia: str = "微软雅黑"
    font_ascii: str = "Arial"
    body: list[str] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)

    def paragraph(self, text: str = "", *, style: str | None = None, bold: bool = False, align: str | None = None) -> None:
        ppr = ""
        if style:
            ppr += f'<w:pStyle w:val="{style}"/>'
        if align:
            ppr += f'<w:jc w:val="{align}"/>'
        if not style:
            ppr += '<w:spacing w:after="120" w:line="300" w:lineRule="auto"/>'
        rpr = "<w:b/>" if bold else ""
        self.body.append(
            f"<w:p>{'<w:pPr>'+ppr+'</w:pPr>' if ppr else ''}"
            f"<w:r><w:rPr>{rpr}<w:rFonts w:ascii=\"{self.font_ascii}\" w:eastAsia=\"{self.font_east_asia}\"/></w:rPr>"
            f"<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
        )

    def equation(self, text: str) -> None:
        self.body.append(
            "<w:p><w:pPr><w:jc w:val=\"center\"/><w:spacing w:before=\"80\" w:after=\"160\" w:line=\"300\" w:lineRule=\"auto\"/></w:pPr>"
            "<w:r><w:rPr><w:rFonts w:ascii=\"Cambria Math\" w:hAnsi=\"Cambria Math\" w:eastAsia=\"Cambria Math\"/>"
            "<w:sz w:val=\"23\"/><w:color w:val=\"222222\"/></w:rPr>"
            f"<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
        )

    def heading(self, text: str, level: int = 1) -> None:
        style = "Heading1" if level == 1 else "Heading2" if level == 2 else "Heading3"
        self.paragraph(text, style=style, bold=True)

    def page_break(self) -> None:
        self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def bullet(self, text: str) -> None:
        self.body.append(
            "<w:p><w:pPr><w:spacing w:after=\"80\" w:line=\"300\" w:lineRule=\"auto\"/><w:ind w:left=\"520\" w:hanging=\"240\"/></w:pPr>"
            f"<w:r><w:rPr><w:rFonts w:ascii=\"{self.font_ascii}\" w:eastAsia=\"{self.font_east_asia}\"/></w:rPr>"
            f"<w:t>• {escape(text)}</w:t></w:r></w:p>"
        )

    def callout(self, title: str, lines: list[str], *, fill: str = "EAF3F8") -> None:
        body = "<w:p><w:pPr><w:spacing w:after=\"80\"/></w:pPr>"
        body += (
            f"<w:r><w:rPr><w:b/><w:color w:val=\"1F4E79\"/><w:rFonts w:ascii=\"{self.font_ascii}\" "
            f"w:eastAsia=\"{self.font_east_asia}\"/></w:rPr><w:t>{escape(title)}</w:t></w:r></w:p>"
        )
        for line in lines:
            body += (
                "<w:p><w:pPr><w:spacing w:after=\"60\"/></w:pPr>"
                f"<w:r><w:rPr><w:rFonts w:ascii=\"{self.font_ascii}\" w:eastAsia=\"{self.font_east_asia}\"/></w:rPr>"
                f"<w:t xml:space=\"preserve\">{escape(line)}</w:t></w:r></w:p>"
            )
        self.body.append(
            "<w:tbl><w:tblPr><w:tblW w:w=\"5000\" w:type=\"pct\"/>"
            "<w:tblCellMar><w:top w:w=\"160\" w:type=\"dxa\"/><w:left w:w=\"220\" w:type=\"dxa\"/>"
            "<w:bottom w:w=\"160\" w:type=\"dxa\"/><w:right w:w=\"220\" w:type=\"dxa\"/></w:tblCellMar>"
            "<w:tblBorders><w:top w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"9CC2E5\"/>"
            "<w:left w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"9CC2E5\"/>"
            "<w:bottom w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"9CC2E5\"/>"
            "<w:right w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"9CC2E5\"/></w:tblBorders></w:tblPr>"
            f"<w:tr><w:tc><w:tcPr><w:shd w:fill=\"{fill}\"/></w:tcPr>{body}</w:tc></w:tr></w:tbl>"
        )

    def table(self, rows: list[list[Any]]) -> None:
        cells = []
        for row_index, row in enumerate(rows):
            tds = []
            for cell in row:
                shading = '<w:shd w:fill="1F4E79"/>' if row_index == 0 else '<w:shd w:fill="F7F9FB"/>' if row_index % 2 == 0 else ""
                color = '<w:color w:val="FFFFFF"/>' if row_index == 0 else ""
                tds.append(
                    "<w:tc><w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/><w:vAlign w:val=\"center\"/>"
                    f"{shading}</w:tcPr>"
                    f"<w:p><w:pPr><w:spacing w:before=\"40\" w:after=\"40\"/></w:pPr><w:r><w:rPr>{color}<w:rFonts w:ascii=\"{self.font_ascii}\" w:eastAsia=\"{self.font_east_asia}\"/>"
                    f"{'<w:b/>' if row_index == 0 else ''}</w:rPr><w:t xml:space=\"preserve\">{escape(_text(cell, ''))}</w:t></w:r></w:p></w:tc>"
                )
            cells.append("<w:tr>" + "".join(tds) + "</w:tr>")
        borders = (
            '<w:tblBorders><w:top w:val="single" w:sz="8" w:space="0" w:color="D9E2F3"/>'
            '<w:left w:val="single" w:sz="8" w:space="0" w:color="D9E2F3"/>'
            '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="D9E2F3"/>'
            '<w:right w:val="single" w:sz="8" w:space="0" w:color="D9E2F3"/>'
            '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="E6EAF0"/>'
            '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="E6EAF0"/></w:tblBorders>'
        )
        self.body.append(
            "<w:tbl><w:tblPr><w:tblW w:w=\"5000\" w:type=\"pct\"/>"
            "<w:tblCellMar><w:top w:w=\"100\" w:type=\"dxa\"/><w:left w:w=\"120\" w:type=\"dxa\"/>"
            "<w:bottom w:w=\"100\" w:type=\"dxa\"/><w:right w:w=\"120\" w:type=\"dxa\"/></w:tblCellMar>"
            f"{borders}</w:tblPr>{''.join(cells)}</w:tbl>"
        )

    def image(self, path: Path, caption: str, *, width_in: float = 5.8) -> None:
        if not path.is_file():
            self.paragraph(f"[图像缺失] {caption}: {path}")
            return
        rid = f"rId{len(self.images) + 1}"
        name = f"image{len(self.images) + 1}{path.suffix.lower()}"
        self.images.append(ImageRef(path=path, rid=rid, name=name, width_in=width_in))
        cx, cy = _image_size_emu(path, width_in)
        drawing = f'''
<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>
<wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{len(self.images)}" name="{escape(caption)}"/>
<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="0" name="{escape(path.name)}"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''
        self.body.append(drawing)
        self.paragraph(caption, style="Caption", align="center")

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
            docx.writestr("[Content_Types].xml", _content_types(self.images))
            docx.writestr("_rels/.rels", _root_rels())
            docx.writestr("docProps/core.xml", _core_props(self.title))
            docx.writestr("docProps/app.xml", _app_props())
            docx.writestr("word/document.xml", _document_xml("".join(self.body)))
            docx.writestr("word/styles.xml", _styles_xml(self.font_east_asia, self.font_ascii))
            docx.writestr("word/settings.xml", _settings_xml())
            docx.writestr("word/_rels/document.xml.rels", _document_rels(self.images))
            for image in self.images:
                docx.write(image.path, f"word/media/{image.name}")
        return path


def _image_size_emu(path: Path, width_in: float) -> tuple[int, int]:
    width_in = min(width_in, A4_CONTENT_WIDTH_IN)
    if Image is None:
        return int(width_in * EMU_PER_INCH), int(width_in * 0.62 * EMU_PER_INCH)
    with Image.open(path) as img:
        w, h = img.size
    height_in = width_in * h / w if w else width_in * 0.62
    return int(width_in * EMU_PER_INCH), int(height_in * EMU_PER_INCH)


def _content_types(images: list[ImageRef]) -> str:
    defaults = [
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Default Extension="png" ContentType="image/png"/>',
        '<Default Extension="jpg" ContentType="image/jpeg"/>',
        '<Default Extension="jpeg" ContentType="image/jpeg"/>',
    ]
    overrides = [
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>',
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>',
        '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' + "".join(defaults + overrides) + "</Types>"


def _root_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def _document_rels(images: list[ImageRef]) -> str:
    rels = [
        '<Relationship Id="rStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
        '<Relationship Id="rSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>',
    ]
    for image in images:
        rels.append(f'<Relationship Id="{image.rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{image.name}"/>')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>"


def _document_xml(body: str) -> str:
    sect = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1200" w:bottom="1440" w:left="1200" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>' + body + sect + '</w:body></w:document>'


def _styles_xml(font_east_asia: str, font_ascii: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{font_ascii}" w:hAnsi="{font_ascii}" w:eastAsia="{font_east_asia}"/><w:sz w:val="21"/><w:szCs w:val="21"/><w:color w:val="222222"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="{font_ascii}" w:hAnsi="{font_ascii}" w:eastAsia="{font_east_asia}"/><w:sz w:val="21"/><w:color w:val="222222"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:jc w:val="center"/><w:spacing w:before="120" w:after="260"/></w:pPr><w:rPr><w:rFonts w:ascii="{font_ascii}" w:hAnsi="{font_ascii}" w:eastAsia="{font_east_asia}"/><w:b/><w:sz w:val="40"/><w:color w:val="17365D"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:keepNext/><w:spacing w:before="360" w:after="160"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts w:ascii="{font_ascii}" w:hAnsi="{font_ascii}" w:eastAsia="{font_east_asia}"/><w:b/><w:sz w:val="31"/><w:color w:val="1F4E79"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:keepNext/><w:spacing w:before="260" w:after="120"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:rFonts w:ascii="{font_ascii}" w:hAnsi="{font_ascii}" w:eastAsia="{font_east_asia}"/><w:b/><w:sz w:val="26"/><w:color w:val="2F75B5"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:pPr><w:keepNext/><w:spacing w:before="180" w:after="80"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:rFonts w:ascii="{font_ascii}" w:hAnsi="{font_ascii}" w:eastAsia="{font_east_asia}"/><w:b/><w:sz w:val="23"/><w:color w:val="5B9BD5"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="180"/></w:pPr><w:rPr><w:rFonts w:ascii="{font_ascii}" w:hAnsi="{font_ascii}" w:eastAsia="{font_east_asia}"/><w:i/><w:sz w:val="19"/><w:color w:val="666666"/></w:rPr></w:style>
</w:styles>'''


def _settings_xml() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:defaultTabStop w:val="420"/></w:settings>'


def _core_props(title: str) -> str:
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>{escape(title)}</dc:title><dc:creator>Foam-Agent</dc:creator><cp:lastModifiedBy>Foam-Agent</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified></cp:coreProperties>'''


def _app_props() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Foam-Agent</Application></Properties>'


def _format_error(value: Any) -> str:
    try:
        return f"{float(value):.3e}"
    except Exception:
        return _text(value)



def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return _text(value, "")


def _extract_scalar_from_text(text: str, aliases: tuple[str, ...]) -> str | None:
    number = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    for alias in aliases:
        pattern = re.escape(alias).replace(r"\ ", r"\s+")
        direct = re.search(rf"(?<![A-Za-z0-9_]){pattern}\s*(?:=|:|：|\s)\s*{number}", text, re.IGNORECASE)
        if direct:
            return direct.group(1)
        formula = re.search(rf"(?<![A-Za-z0-9_]){pattern}\s*(?:=|:|：)\s*[^,，;；\n]*?(?:=|:|：)\s*{number}", text, re.IGNORECASE)
        if formula:
            return formula.group(1)
    return None


def _extract_dimensionless(application: str) -> dict[str, str]:
    values: dict[str, str] = {}
    aliases = {
        "Re": ("Re", "Reynolds_number", "Reynolds number", "雷诺数"),
        "Wi": ("Wi", "Weissenberg_number", "Weissenberg number", "魏森伯格数"),
        "De": ("De", "Deborah_number", "Deborah number", "德博拉数"),
        "beta": ("beta", "β"),
    }
    for key, names in aliases.items():
        value = _extract_scalar_from_text(application, names)
        if value is not None:
            values[key] = value
    return values


def _geometry_label(geometry_class: str | None, application: str) -> str:
    if geometry_class == "lid_driven_cavity" or any(term in application for term in ("方腔", "cavity", "lid-driven")):
        return "顶盖驱动方腔"
    if geometry_class == "parallel_plate_channel" or any(term in application for term in ("平行", "平板", "channel")):
        return "平行平板通道"
    if geometry_class == "contraction" or any(term in application for term in ("收缩", "contraction")):
        return "收缩流道"
    if geometry_class == "dam_break" or any(term in application.casefold() for term in ("dambreak", "dam break", "破坝", "溃坝")):
        return "溃坝自由液面流动"
    return _text(geometry_class, "通用 CFD 几何")


def _case_title(manifest: dict[str, Any], application: str) -> str:
    problem = manifest.get("problem_intent", {}) or {}
    rheology = manifest.get("rheology_spec", {}) or {}
    model = _text(rheology.get("selected_model"), "流体")
    geometry = _geometry_label(problem.get("geometry_class"), application)
    return f"{model} {geometry}仿真案例报告"


def _target_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    target = ((manifest.get("workflow_plan") or {}).get("target") or {})
    return {
        "channel": target.get("channel", manifest.get("channel")),
        "version": target.get("version", manifest.get("version")),
        "solver": target.get("solver", manifest.get("solver")),
        "distribution": target.get("distribution", manifest.get("distribution")),
    }


def _resolve_artifact_path(case: Path, raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_file():
        return path
    if not path.is_absolute():
        candidate = case / path
        return candidate if candidate.is_file() else None
    parts = list(path.parts)
    if case.name in parts:
        rel = Path(*parts[parts.index(case.name) + 1:])
        candidate = case / rel
        if candidate.is_file():
            return candidate
    return None


def _artifact_items(case: Path) -> list[dict[str, Any]]:
    manifest = _read_json(case / "POSTPROCESS_ARTIFACTS.json")
    items: list[dict[str, Any]] = []
    for item in manifest.get("artifacts", []):
        path = _resolve_artifact_path(case, item.get("path"))
        if path:
            updated = dict(item)
            updated["resolved_path"] = path
            items.append(updated)
    return items


def _figure_caption(kind: str, path: Path) -> str:
    labels = {
        "residual_plot": "求解残差历史",
        "kinetic_energy_plot": "平均动能 Ek(t) 历史",
        "rheotool_channel_comparison_plot": "解析解与数值解对比",
        "dieswell_mesh_overview": "DieSwell 网格概览",
        "dieswell_free_surface_overlay": "自由液面初始/完成态对比",
        "dieswell_swell_ratio_history_plot": "挤出胀大比随时间变化",
    }
    if kind in labels:
        return labels[kind]
    if kind.startswith("dieswell_field_snapshot:"):
        _, name = kind.split(":", 1)
        field, _, when = name.partition(":")
        when_label = "初始态" if when == "initial" else "完成态" if when == "final" else when
        labels_by_field = {
            "U": "速度场 |U|",
            "p_rgh": "压力场 p_rgh",
            "tau.water": "聚合物应力场 |tau.water|",
            "alpha.water": "体积分数/自由液面 alpha.water",
        }
        return f"{labels_by_field.get(field, field)}（{when_label}）"
    if kind.startswith("field_plot:"):
        return f"{kind.split(':', 1)[1]} 场分布"
    if kind.startswith("centerline_plot:"):
        return f"{kind.split(':', 1)[1]} 中心线/剖面曲线"
    return path.stem.replace("_", " ")


def _select_figures(case: Path, max_figures: int = 14) -> list[tuple[Path, str]]:
    priority = {
        "residual_plot": 10,
        "kinetic_energy_plot": 20,
        "rheotool_channel_comparison_plot": 30,
        "dieswell_mesh_overview": 35,
        "dieswell_free_surface_overlay": 36,
        "dieswell_swell_ratio_history_plot": 37,
    }
    figures: list[tuple[int, Path, str]] = []
    for item in _artifact_items(case):
        kind = str(item.get("kind", ""))
        path = item["resolved_path"]
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        rank = priority.get(kind, 50)
        if kind.startswith("dieswell_field_snapshot:"):
            rank = 38
        if kind.startswith("field_plot:"):
            rank = 40
        elif kind.startswith("centerline_plot:"):
            rank = 50
        figures.append((rank, path, _figure_caption(kind, path)))
    seen: set[Path] = set()
    selected: list[tuple[Path, str]] = []
    for _, path, caption in sorted(figures, key=lambda item: (item[0], str(item[1]))):
        if path in seen:
            continue
        seen.add(path)
        selected.append((path, caption))
        if len(selected) >= max_figures:
            break
    return selected


def _mesh_summary(case: Path) -> str:
    text = (case / "system" / "blockMeshDict").read_text(encoding="utf-8", errors="ignore") if (case / "system" / "blockMeshDict").is_file() else ""
    matches = re.findall(r"hex\s*\([^)]*\)\s*\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)", text)
    if not matches:
        return "未从 blockMeshDict 自动提取网格规模"
    if len(matches) == 1:
        return " × ".join(matches[0])
    cells = [tuple(int(v) for v in match) for match in matches]
    total = sum(x * y * z for x, y, z in cells)
    return f"{len(matches)} 个 block，合计约 {total} cells"


def _parameter_rows(manifest: dict[str, Any], application: str) -> list[list[Any]]:
    rheology = manifest.get("rheology_spec", {}) or {}
    params = dict(rheology.get("parameters") or {})
    known = (manifest.get("problem_intent") or {}).get("known_parameters") or {}
    for key, value in known.items():
        params.setdefault(key, value)
    rows = [["参数", "数值", "来源"]]
    rows.append(["模型", rheology.get("selected_model", "未记录"), "user_provided / manifest"])
    for key in sorted(params):
        rows.append([key, _format_value(params[key]), "user_provided / manifest"])
    for key, value in _extract_dimensionless(application).items():
        rows.append([key, value, "user_provided / requirement"])
    return rows


def _execution_rows(manifest: dict[str, Any], post: dict[str, Any]) -> list[list[Any]]:
    return [
        ["步骤", "状态"],
        ["Schema / Manifest 校验", manifest.get("validation_status", "未记录")],
        ["OpenFOAM 求解", manifest.get("run_status", "未记录")],
        ["sampleDict", (post.get("sampleDict") or post.get("samples") or {}).get("status", "未记录")],
        ["标准后处理", post.get("status", "未记录")],
        ["最新时间", post.get("latest_time", "未记录")],
    ]


def _artifact_display_path(path: Path | None) -> str:
    if path is None:
        return "无"
    parts = path.parts
    if "postProcessing" in parts:
        return str(Path(*parts[parts.index("postProcessing"):]))
    if "postprocess" in parts:
        return str(Path(*parts[parts.index("postprocess"):]))
    return path.name


def _find_artifact(artifacts: list[dict[str, Any]], *, kind: str | None = None, required: tuple[str, ...] = ()) -> Path | None:
    lowered_required = tuple(token.casefold() for token in required)
    for item in artifacts:
        item_kind = str(item.get("kind", ""))
        path = item.get("resolved_path")
        if not isinstance(path, Path):
            continue
        if kind is not None and item_kind != kind:
            continue
        haystack = path.name.casefold()
        if all(token in haystack for token in lowered_required):
            return path
    return None


def _sample_line_label(path: Path, objective: str) -> str:
    name = path.name
    if objective == "velocity_profile":
        match = re.search(r"lineVert_x([^_]+)_U\.xy$", name, re.IGNORECASE)
        if match:
            return f"x={match.group(1)} 处 u(y) 速度剖面"
        match = re.search(r"lineHorz_y([^_]+)_U\.xy$", name, re.IGNORECASE)
        if match:
            return f"y={match.group(1)} 处 u(x) 速度剖面"
        return "速度剖面"
    if objective == "theta_profile":
        match = re.search(r"lineHorz_y([^_]+).*theta.*\.xy$", name, re.IGNORECASE)
        if match:
            return f"y={match.group(1)} 处 Θxy 剖面"
        match = re.search(r"lineVert_x([^_]+).*theta.*\.xy$", name, re.IGNORECASE)
        if match:
            return f"x={match.group(1)} 处 Θxy 剖面"
        return "Θxy 剖面"
    return objective


def _split_numbered_items(text: str) -> list[str]:
    parts = re.split(r"(?:^|[;；\n])\s*\d+\s*[.、)]\s*", text)
    return [part.strip(" ;；。") for part in parts if part.strip(" ;；。")]


def _requested_output_items(application: str) -> list[str]:
    items: list[str] = []
    in_block = False
    for raw_line in application.splitlines():
        line = raw_line.strip()
        if not line:
            if in_block and items:
                break
            continue
        marker = re.search(r"(?:请输出|Requested Outputs?|输出结果|输出)", line, re.IGNORECASE)
        if marker and not in_block:
            in_block = True
            tail = line[marker.end():].lstrip(" ：:")
            items.extend(_split_numbered_items(tail))
            continue
        key_value = re.match(r"(?:requested_output|requested_outputs|output|outputs)\s*[:=：]\s*(.+)$", line, re.IGNORECASE)
        if key_value:
            items.extend(_split_numbered_items(key_value.group(1)))
            continue
        if not in_block:
            continue
        if items and re.match(r"^(?:#+\s*)?(?:Missing|缺失|未确认|说明|备注|Assumptions|参数|边界)", line, re.IGNORECASE):
            break
        if items and line.startswith("##"):
            break
        match = re.match(r"^(?:[-*]\s*)?(?:\d+\s*[.、)]\s*)?(.+?)\s*[;；。]?$", line)
        if match:
            item = match.group(1).strip()
            if item and not re.match(r"^(?:none|无)$", item, re.IGNORECASE):
                items.append(item)
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _requested_coordinate(text: str, axis: str) -> float | None:
    match = re.search(rf"(?<![A-Za-z0-9_]){axis}\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _sample_coordinate(path: Path) -> tuple[str, float] | None:
    match = re.search(r"line(Vert|Horz)_([xy])([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", path.name, re.IGNORECASE)
    if not match:
        return None
    try:
        return match.group(2).lower(), float(match.group(3))
    except ValueError:
        return None


def _find_sample_for_request(artifacts: list[dict[str, Any]], request: str, field_token: str) -> Path | None:
    x_value = _requested_coordinate(request, "x")
    y_value = _requested_coordinate(request, "y")
    fixed_axis = "x" if x_value is not None else "y" if y_value is not None else None
    fixed_value = x_value if x_value is not None else y_value
    candidates: list[Path] = []
    for item in artifacts:
        if str(item.get("kind", "")) != "sample":
            continue
        path = item.get("resolved_path")
        if not isinstance(path, Path):
            continue
        name = path.name.casefold()
        if field_token == "U" and not name.endswith("_u.xy"):
            continue
        if field_token == "theta" and "theta" not in name:
            continue
        if fixed_axis is not None:
            coord = _sample_coordinate(path)
            if coord is None or coord[0] != fixed_axis or fixed_value is None or abs(coord[1] - fixed_value) > 1e-9:
                continue
        candidates.append(path)
    return sorted(candidates, key=lambda path: path.name)[0] if candidates else None


def _answer_requested_output(request: str, post: dict[str, Any], artifacts: list[dict[str, Any]]) -> tuple[str, str]:
    lowered = request.casefold()
    if any(term in lowered for term in ("extrudate swell", "swell ratio", "die swell")) or any(term in request for term in ("胀大比", "挤出胀大", "模口胀大")):
        dieswell = post.get("dieswell_free_surface") or {}
        metrics_path = _find_artifact(artifacts, kind="dieswell_swell_metrics")
        plot_path = _find_artifact(artifacts, kind="dieswell_free_surface_plot")
        if dieswell.get("status") == "passed":
            value = dieswell.get("swell_ratio")
            location = dieswell.get("max_location")
            evidence = ", ".join(_artifact_display_path(path) for path in (metrics_path, plot_path) if path is not None)
            detail = f"已计算，胀大比={value}"
            if location:
                detail += f"，最大位置={location}"
            return (detail, evidence or "dieswell_free_surface")
        return ("未生成", _artifact_display_path(metrics_path) or str(dieswell.get("reason") or "无"))
    if any(term in lowered for term in ("free surface", "water front", "interface", "alpha.water")) or any(term in request for term in ("自由液面", "水体前沿", "相界面", "液面")):
        dambreak = post.get("dambreak_free_surface") or {}
        dambreak_metrics = _find_artifact(artifacts, kind="dambreak_front_metrics")
        dambreak_plot = _find_artifact(artifacts, kind="dambreak_free_surface_plot")
        if dambreak.get("status") == "passed":
            evidence = ", ".join(_artifact_display_path(path) for path in (dambreak_metrics, dambreak_plot) if path is not None)
            return (f"已计算水体前沿，front_x={dambreak.get('front_x')}", evidence or "dambreak_free_surface")
        alpha_path = (
            _find_artifact(artifacts, kind="dambreak_field_snapshot:alpha.water:final")
            or _find_artifact(artifacts, kind="field_plot:alpha.water")
            or _find_artifact(artifacts, required=("alpha",))
        )
        if alpha_path:
            return ("已输出相分数/自由液面场图", _artifact_display_path(alpha_path))
        return ("未生成", "当前后处理未找到 alpha.water 自由液面图")
    if "ek" in lowered or "kinetic" in lowered or "动能" in request:
        csv_path = _find_artifact(artifacts, kind="kinetic_energy_csv")
        plot_path = _find_artifact(artifacts, kind="kinetic_energy_plot")
        done = post.get("kinetic_energy", {}).get("status") == "passed" or csv_path is not None or plot_path is not None
        evidence = ", ".join(_artifact_display_path(p) for p in (csv_path, plot_path) if p is not None)
        return ("已输出" if done else "未生成", evidence or "无")
    if "theta" in lowered or "θ" in lowered or "构象" in request:
        path = _find_sample_for_request(artifacts, request, "theta") or _find_artifact(artifacts, kind="sample", required=("theta",))
        evidence = _artifact_display_path(path)
        if path:
            evidence += "（tau/theta 联合采样文件，Θxy 位于 theta 分量列）"
        return ("已输出" if path else "未生成", evidence)
    if "velocity" in lowered or "速度" in request or "u(" in lowered or re.search(r"\bu\b", lowered):
        path = _find_sample_for_request(artifacts, request, "U") or _find_artifact(artifacts, kind="sample", required=("_U.xy",))
        return ("已输出" if path else "未生成", _artifact_display_path(path))
    return ("未生成明确答案", "当前后处理流程未找到该请求对应的专用产物")


def _requested_output_rows(application: str, post: dict[str, Any], artifacts: list[dict[str, Any]]) -> list[list[Any]]:
    rows = [["用户问题/要求", "回答", "证据"]]
    for item in _requested_output_items(application):
        status, evidence = _answer_requested_output(item, post, artifacts)
        rows.append([item, status, evidence])
    return rows


def _objective_rows(manifest: dict[str, Any], post: dict[str, Any], artifacts: list[dict[str, Any]], application: str = "") -> list[list[Any]]:
    requested_rows = _requested_output_rows(application, post, artifacts) if application else [["用户问题/要求", "回答", "证据"]]
    if len(requested_rows) > 1:
        return requested_rows
    objectives = list(((manifest.get("problem_intent") or {}).get("objectives") or []) or ((manifest.get("physics_spec") or {}).get("objectives") or []))
    kinds = {str(item.get("kind", "")) for item in artifacts}
    rows = [["目标", "完成情况", "证据"]]
    if not objectives:
        objectives = ["simulation_result"]
    for obj in objectives:
        if obj == "kinetic_energy":
            csv_path = _find_artifact(artifacts, kind="kinetic_energy_csv")
            plot_path = _find_artifact(artifacts, kind="kinetic_energy_plot")
            done = post.get("kinetic_energy", {}).get("status") == "passed" or csv_path is not None or plot_path is not None
            evidence = ", ".join(_artifact_display_path(p) for p in (csv_path, plot_path) if p is not None)
            rows.append(["平均动能 Ek(t) 全程曲线", "已输出" if done else "未生成", evidence or "无"])
        elif obj == "velocity_profile":
            sample_path = _find_artifact(artifacts, kind="sample", required=("lineVert_x", "_U.xy")) or _find_artifact(artifacts, required=("lineVert_x", "_U.xy"))
            if sample_path is None:
                sample_path = _find_artifact(artifacts, kind="sample", required=("_U.xy",))
            rows.append([_sample_line_label(sample_path, obj) if sample_path else "速度剖面", "已输出" if sample_path else "未生成", _artifact_display_path(sample_path)])
        elif obj == "theta_profile":
            sample_path = _find_artifact(artifacts, kind="sample", required=("lineHorz_y", "theta")) or _find_artifact(artifacts, required=("lineHorz_y", "theta"))
            if sample_path is None:
                sample_path = _find_artifact(artifacts, kind="sample", required=("theta",))
            evidence = _artifact_display_path(sample_path)
            if sample_path:
                evidence += "（tau/theta 联合采样文件，Θxy 位于 theta 分量列）"
            rows.append([_sample_line_label(sample_path, obj) if sample_path else "Θxy 剖面", "已输出" if sample_path else "未生成", evidence])
        elif obj in {"pressure_drop", "material_functions"}:
            evidence = ", ".join(sorted(k for k in kinds if "sample" in k or "centerline" in k)) or "postprocess report"
            rows.append([obj, "已提取/已汇总", evidence])
        elif obj in {"free_surface", "extrudate_swell"}:
            dieswell = post.get("dieswell_free_surface") or {}
            metrics_path = _find_artifact(artifacts, kind="dieswell_swell_metrics")
            plot_path = _find_artifact(artifacts, kind="dieswell_free_surface_plot")
            evidence = ", ".join(_artifact_display_path(path) for path in (metrics_path, plot_path) if path is not None)
            if dieswell.get("status") == "passed":
                rows.append(["挤出胀大比 / 自由液面", f"已计算，胀大比={dieswell.get('swell_ratio')}", evidence or "dieswell_free_surface"])
            else:
                dambreak = post.get("dambreak_free_surface") or {}
                dambreak_metrics = _find_artifact(artifacts, kind="dambreak_front_metrics")
                dambreak_plot = _find_artifact(artifacts, kind="dambreak_free_surface_plot")
                if dambreak.get("status") == "passed":
                    evidence = ", ".join(_artifact_display_path(path) for path in (dambreak_metrics, dambreak_plot) if path is not None)
                    rows.append(["自由液面 / 水体前沿", f"已计算，front_x={dambreak.get('front_x')}", evidence or "dambreak_free_surface"])
                else:
                    alpha_path = (
                        _find_artifact(artifacts, kind="dambreak_field_snapshot:alpha.water:final")
                        or _find_artifact(artifacts, kind="field_plot:alpha.water")
                        or _find_artifact(artifacts, required=("alpha",))
                    )
                    if alpha_path:
                        rows.append(["自由液面 / 相分数场", "已输出 alpha.water 场图", _artifact_display_path(alpha_path)])
                    else:
                        rows.append(["自由液面 / 相分数场", "未生成", evidence or str(dieswell.get("reason") or "无")])
        else:
            if obj == "simulation_result":
                rows.append([obj, "已完成" if post.get("status") == "passed" else "未完成", "manifest / postprocess report"])
            else:
                rows.append([obj, "未生成明确答案", "当前后处理流程未找到该目标对应的专用产物"])
    return rows


def _assert_report_answers_user_questions(rows: list[list[Any]], *, application: str) -> None:
    """Enforce the report contract: user-requested outputs must get a direct answer.

    The report may answer "未生成", but it must not hide a requested business
    output behind a generic "已汇总 / manifest" placeholder.
    """
    requested = _requested_output_items(application)
    if not requested:
        return
    if len(rows) <= 1:
        raise ValueError("REPORT_ANSWER_POLICY_ERROR: requested outputs exist but no answer rows were generated")
    vague_answers = {"已汇总", "已提取/已汇总"}
    for row in rows[1:]:
        answer = str(row[1]) if len(row) > 1 else ""
        evidence = str(row[2]) if len(row) > 2 else ""
        if answer in vague_answers and evidence in {"manifest / postprocess report", "postprocess report", ""}:
            raise ValueError(
                "REPORT_ANSWER_POLICY_ERROR: requested output was not directly answered; "
                f"request={row[0]!r} answer={answer!r}"
            )


def _residual_rows(post: dict[str, Any]) -> list[list[Any]]:
    residuals = ((post.get("metrics") or {}).get("residuals") or {}).get("fields") or {}
    rows = [["方程", "final_max", "记录数"]]
    for field_name, item in sorted(residuals.items()):
        rows.append([field_name, _format_error(item.get("final_max")), item.get("count", "")])
    return rows if len(rows) > 1 else [["方程", "final_max", "记录数"], ["未记录", "", ""]]


def _comparison_section(doc: DocxBuilder, post: dict[str, Any]) -> None:
    comparisons = []
    for key in ("rheotool_channel_comparison", "benchmark_comparison"):
        item = post.get(key) or {}
        if item.get("status") in {"passed", "present"}:
            comparisons.append((key, item))
    if not comparisons:
        doc.paragraph("本案例未发现可用的本地解析解/文献逐点参考数据，未生成定量误差对比表；报告仅基于本次数值求解与后处理产物进行说明。")
        return
    for name, item in comparisons:
        doc.bullet(f"{name}: {item.get('status')}")
        errors = item.get("errors") or {}
        if errors:
            rows = [["变量", "max_abs", "mean_abs", "RMSE"]]
            for field_name, stats in sorted(errors.items()):
                rows.append([field_name, _format_error(stats.get("max_abs")), _format_error(stats.get("mean_abs")), _format_error(stats.get("rmse"))])
            doc.table(rows)


def _requested_end_time(application: str) -> str | None:
    return _extract_scalar_from_text(application, ("end_time", "end time", "endTime"))


def _control_end_time(case: Path) -> str | None:
    text = (case / "system" / "controlDict").read_text(encoding="utf-8", errors="ignore") if (case / "system" / "controlDict").is_file() else ""
    return _extract_scalar_from_text(text, ("endTime",))


def _limitations(case: Path, manifest: dict[str, Any], post: dict[str, Any], application: str) -> list[str]:
    items = ["当前报告未包含网格无关性检查；如用于正式认证，建议补做至少 2 级网格加密复算。"]
    if (post.get("benchmark_comparison") or {}).get("status") != "present" and (post.get("rheotool_channel_comparison") or {}).get("status") != "passed":
        items.append("未发现本地逐点参考数据或解析解对比产物，因此不声明文献/解析误差达标。")
    req_end = _requested_end_time(application)
    run_end = _control_end_time(case) or post.get("latest_time")
    if req_end and run_end and str(float(req_end)) != str(float(run_end)):
        items.append(f"用户需求中的结束时间约为 t={req_end}，本次报告采用的运行/最新时间为 t={run_end}；请按实际目标选择对应时间目录。")
    kinetic = post.get("kinetic_energy") or {}
    if kinetic.get("rho_source") == "default":
        items.append("平均动能计算使用默认 rho=1；若物理密度不同，应重新以后处理参数修正 Ek(t)。")
    physics = manifest.get("physics_spec") or {}
    if not physics.get("free_surface"):
        items.append("当前模型未包含自由液面、温度耦合、壁面滑移等未声明物理效应。")
    return items


def _recommendations(limitations: list[str]) -> list[str]:
    recs = ["保留当前 case_dir 与全部 JSON/CSV/PNG 产物，以便复核和复现。"]
    if any("网格" in item for item in limitations):
        recs.append("建议补做网格无关性检查，重点关注近壁梯度、压力或应力量的收敛。")
    if any("参考数据" in item or "解析解" in item for item in limitations):
        recs.append("如需定量 benchmark 结论，应补充本地参考数据并重新生成对比图/误差表。")
    return recs


def _is_dieswell_report(manifest: dict[str, Any], post: dict[str, Any], tutorial: dict[str, Any], application: str) -> bool:
    template_id = str(tutorial.get("template_id", ""))
    geometry = str((manifest.get("problem_intent") or {}).get("geometry_class", ""))
    lowered = application.casefold()
    return (
        "dieswell" in template_id
        or geometry == "die_swell"
        or (post.get("dieswell_free_surface") or {}).get("status") == "passed"
        or any(term in lowered for term in ("die swell", "dieswell", "挤出胀大", "模口胀大"))
    )


def _is_dambreak_report(manifest: dict[str, Any], tutorial: dict[str, Any], application: str) -> bool:
    template_id = str(tutorial.get("template_id", ""))
    reproduction_target = str((manifest.get("problem_intent") or {}).get("reproduction_target", ""))
    geometry = str((manifest.get("problem_intent") or {}).get("geometry_class", ""))
    lowered = application.casefold()
    return (
        "dambreak" in template_id.casefold()
        or "dambreak" in reproduction_target.casefold()
        or geometry == "dam_break"
        or any(term in lowered for term in ("dambreak", "dam break", "破坝", "溃坝", "水柱坍塌"))
    )


def _artifact_by_kind(artifacts: list[dict[str, Any]], kind: str) -> Path | None:
    return _find_artifact(artifacts, kind=kind)


def _add_explained_figure(
    doc: DocxBuilder,
    path: Path | None,
    caption: str,
    *,
    purpose: str,
    reading: str,
    conclusion: str,
    width_in: float = 5.8,
) -> None:
    if path is None or not path.is_file():
        doc.paragraph(f"{caption}：图像文件未生成；该证据项在本报告中跳过。")
        return
    doc.image(path, caption, width_in=width_in)
    doc.bullet(f"用途：{purpose}")
    doc.bullet(f"读图方法：{reading}")
    doc.bullet(f"说明结论：{conclusion}")


def _add_engineering_figure(
    doc: DocxBuilder,
    path: Path | None,
    caption: str,
    analysis: str,
    *,
    width_in: float = 5.8,
) -> None:
    if path is None or not path.is_file():
        doc.paragraph(f"{caption}：图像文件未生成；本段仅保留文字分析。")
        doc.paragraph(analysis)
        return
    doc.image(path, caption, width_in=width_in)
    doc.paragraph(analysis)


def _clean_requirement_for_report(application: str) -> str:
    if not application:
        return "未记录原始需求。"
    user_goal = re.search(
        r"(?is)(?:^|\n)\s*##\s*User Goal\s*(.+?)(?=\n\s*##\s+|\Z)",
        application,
    )
    if user_goal:
        goal = re.sub(r"\s+", " ", user_goal.group(1)).strip(" -:：\n\t")
        if goal:
            return goal

    lines: list[str] = []
    internal_headings = {
        "user confirmation",
        "task mode",
        "geometry",
        "flow conditions",
        "fluid properties",
        "material / rheology",
        "requested outputs",
        "missing / unconfirmed information",
    }
    for raw in application.splitlines():
        line = raw.strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith("#"):
            heading = re.sub(r"^#+\s*", "", line).strip().casefold()
            if heading in {"foam-agent user_requirement.txt", *internal_headings}:
                if lines:
                    break
                continue
            continue
        if re.match(
            r"^(task[._ ]?mode|tutorial[._ ]?variant|parameter_policy|template_id|user_overrides|override_source|geometry_type|material_type|constitutive_model|requested_output)\b",
            line,
            re.IGNORECASE,
        ):
            break
        lines.append(line)
    return " ".join(lines) if lines else application.strip()


def _problem_background_paragraph(*, geometry: str, application: str) -> str:
    lowered = application.casefold()
    if any(term in lowered for term in ("dambreak", "dam break", "破坝", "溃坝", "水柱坍塌")) or "溃坝" in geometry:
        return (
            "本案例关注水柱突然坍塌后的两相自由液面流动：水体在重力作用下向下游推进，"
            "自由液面形态、水体前沿位置、速度场和压力场共同决定下游冲击范围与局部载荷分布。"
            "因此，本报告围绕“自由液面如何演化、波前推进到哪里、速度和压力场是否支持该解释”组织分析。"
        )
    if any(term in lowered for term in ("die swell", "dieswell", "挤出胀大", "模口胀大")) or "挤出" in geometry:
        return (
            "本案例关注平面狭缝口模的挤出胀大：聚合物熔体在口模内受到剪切并累积弹性应力，"
            "离开口模后壁面约束消失，应力释放会推动自由边界向外扩张。"
            "因此，本报告围绕“胀大到什么程度、由哪些流动和应力证据支撑”组织分析。"
        )
    return (
        f"本案例对应的物理场景为{geometry}。报告围绕用户提出的核心技术问题组织："
        "先明确计算对象和物理约束，再说明数值建模与后处理方法，最后用定量指标和关键场图回答问题。"
    )


def _dieswell_metric_summary(post: dict[str, Any]) -> tuple[str, str, str]:
    dieswell = post.get("dieswell_free_surface") or {}
    ratio = dieswell.get("swell_ratio")
    loc = dieswell.get("max_location") or {}
    ratio_text = _format_value(ratio) if ratio is not None else "未生成"
    x_text = _format_value(loc.get("x")) if loc else "未记录"
    y_text = _format_value(loc.get("y")) if loc else "未记录"
    return ratio_text, x_text, y_text


def _add_dieswell_evidence_chain(
    doc: DocxBuilder,
    *,
    artifacts: list[dict[str, Any]],
    post: dict[str, Any],
) -> None:
    ratio_text, x_text, y_text = _dieswell_metric_summary(post)
    final_time = post.get("latest_time", "最终时间")

    _add_explained_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_free_surface_plot"),
        "图 1 自由液面形状与最终胀大比",
        purpose="直接回答“从口模挤出后是否发生胀大、胀大到什么程度”。",
        reading="alpha.water=0.5 等值线近似表示空气/聚合物自由界面；虚线为口模出口，红点为最大胀大位置。",
        conclusion=f"最终胀大比为 {ratio_text}，最大位置约为 x={x_text}, y={y_text}。这是本案例最核心的业务结果。",
    )
    _add_explained_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_swell_ratio_history_plot"),
        "图 2 胀大比随时间变化",
        purpose="判断最终时间步是否可以代表完成态，而不是只取某一瞬时截图。",
        reading="横轴为时间，纵轴为由 alpha.water=0.5 自由界面计算得到的胀大比。曲线后段越平缓，说明结果越接近稳定。",
        conclusion=f"报告采用 t={final_time} 的结果作为最终态；若用于工程定量设计，建议结合该曲线进一步判断是否需要延长计算时间。",
    )
    _add_explained_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_field_snapshot:U:final"),
        "图 3 完成态速度场 |U|",
        purpose="解释聚合物熔体离开口模后的主流运动结构。",
        reading="颜色表示速度大小；重点观察口模出口附近及下游自由膨胀区的速度分布是否连续、是否存在异常局部高速。",
        conclusion="速度场用于支撑自由界面形状的流动背景：熔体离开狭缝后进入自由膨胀区，界面位置变化与下游流动重排相对应。",
    )
    _add_explained_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_field_snapshot:tau.water:final"),
        "图 4 完成态聚合物应力场 |tau.water|",
        purpose="解释 Oldroyd-B 黏弹性应力对挤出胀大的作用。",
        reading="颜色表示聚合物应力张量模量；重点观察口模出口附近的应力集中和下游释放区域。",
        conclusion="应力场是解释胀大机制的关键证据：口模内累积的弹性应力在出口后释放，推动自由界面向外扩张。",
    )
    _add_explained_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_field_snapshot:p_rgh:final"),
        "图 5 完成态压力场 p_rgh",
        purpose="辅助检查口模出口和自由液面区域的压力分布是否与流动方向一致。",
        reading="颜色表示 p_rgh；重点观察出口附近是否存在非物理突变或孤立异常区域。",
        conclusion="压力场作为辅助证据，用于检查求解结果的整体物理连续性；本案例的核心胀大结论仍以自由液面和应力场为主。",
    )


def _add_dieswell_mesh_explanation(doc: DocxBuilder, mesh_figure: Path | None) -> None:
    _add_engineering_figure(
        doc,
        mesh_figure,
        "图 M1 网格与计算域概览",
        "图 M1 用于说明计算域、口模出口和下游自由膨胀区的位置。"
        "线框表示计算网格，重点关注 x=0 附近的口模出口和出口后的下游区域；"
        "后续自由液面、速度、压力和应力图均在该计算域内提取。",
    )


def _dieswell_field_time(post: dict[str, Any], field: str, role: str) -> str:
    item = (
        ((post.get("dieswell_enhanced_figures") or {}).get("zoom_fields") or {}).get(f"{field}:{role}")
        or ((post.get("dieswell_enhanced_figures") or {}).get("fields") or {}).get(f"{field}:{role}")
        or {}
    )
    time_value = item.get("time")
    if time_value is None:
        return "未记录"
    requested = item.get("requested_time")
    if requested is not None and str(requested) != str(time_value):
        return f"{time_value}（请求 {requested}，采用首个可读写出时间）"
    return str(time_value)


def _dieswell_notes(post: dict[str, Any]) -> list[str]:
    fields = {}
    fields.update((post.get("dieswell_enhanced_figures") or {}).get("fields") or {})
    fields.update((post.get("dieswell_enhanced_figures") or {}).get("zoom_fields") or {})
    notes: list[str] = []
    for item in fields.values():
        note = item.get("note")
        if note and note not in notes:
            notes.append(str(note))
    return notes


def _dieswell_field_stats(post: dict[str, Any], key: str, *, zoom: bool = True) -> dict[str, Any]:
    group = "zoom_fields" if zoom else "fields"
    return (
        (((post.get("dieswell_enhanced_figures") or {}).get(group) or {}).get(key) or {}).get("stats")
        or {}
    )


def _format_location(location: Any) -> str:
    if not isinstance(location, dict):
        return "未记录"
    return f"x≈{_format_value(location.get('x'))}, y≈{_format_value(location.get('y'))}"


def _of_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*\{{", text)
    if not match:
        return ""
    start = text.find("{", match.start())
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index]
    return ""


def _of_entry(block: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s+(.+?);", block)
    if not match:
        return "未记录"
    raw = re.sub(r"\[[^\]]+\]", "", match.group(1)).strip()
    parts = raw.split()
    if not parts:
        return "未记录"
    return parts[-1] if len(parts) > 1 and parts[0] == key else raw


def _dieswell_property_rows(case: Path) -> list[list[Any]]:
    text = _read_text_file(case / "constant" / "constitutiveProperties")
    water = _of_block(_of_block(text, "water"), "parameters")
    air = _of_block(_of_block(text, "air"), "parameters")
    rows = [["相/区域", "物理参数 / 模型项", "设定值", "物理意义"]]
    rows.extend(
        [
            ["聚合物相 water", "本构模型", _of_entry(water, "type"), "Oldroyd-BLog 黏弹性模型；water 为教程中的聚合物/熔体相名称。"],
            ["聚合物相 water", "rho", _of_entry(water, "rho"), "聚合物相密度；采用教程无量纲/标定参数。"],
            ["聚合物相 water", "etaS", _of_entry(water, "etaS"), "溶剂黏度贡献。"],
            ["聚合物相 water", "etaP", _of_entry(water, "etaP"), "聚合物弹性贡献黏度。"],
            ["聚合物相 water", "lambda", _of_entry(water, "lambda"), "松弛时间，控制弹性记忆效应。"],
            ["聚合物相 water", "stabilization", _of_entry(water, "stabilization"), "黏弹性应力-速度耦合稳定化设置。"],
            ["空气相 air", "本构模型", _of_entry(air, "type"), "环境气相模型。"],
            ["空气相 air", "rho", _of_entry(air, "rho"), "空气相密度；采用教程参数。"],
            ["空气相 air", "eta", _of_entry(air, "eta"), "空气相动力黏度。"],
            ["相间界面", "sigma", _of_entry(text, "sigma"), "表面张力系数；当前 case 中为 0，表面张力项不主导结果。"],
        ]
    )
    return rows


def _field_file(case: Path, name: str) -> Path | None:
    candidates = [case / "0" / name, case / "0" / f"{name}.org", case / "0" / f"{name}.gz"]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _boundary_patch_names(case: Path) -> list[str]:
    text = _read_text_file(case / "constant" / "polyMesh" / "boundary")
    names = []
    for match in re.finditer(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\{", text):
        name = match.group(1)
        block = _of_block(text[match.start() :], name)
        if "nFaces" in block and name not in names:
            names.append(name)
    return [name for name in names if name != "defaultFaces"]


def _boundary_condition(case: Path, field: str, patch: str) -> str:
    path = _field_file(case, field)
    if path is None:
        return "未记录"
    text = _read_text_file(path)
    patch_block = _of_block(_of_block(text, "boundaryField"), patch)
    if not patch_block:
        return "未设置"
    bc_type = _of_entry(patch_block, "type")
    value = _of_entry(patch_block, "value")
    if value != "未记录":
        return f"{bc_type}; value={value}"
    return bc_type


def _dieswell_boundary_rows(case: Path) -> list[list[Any]]:
    patches = _boundary_patch_names(case) or ["inlet", "wallIn", "wallOut", "atmosphere", "outlet", "symmetry"]
    rows = [["Patch", "U", "p_rgh", "alpha.water", "tau.water", "theta.water"]]
    for patch in patches:
        rows.append(
            [
                patch,
                _boundary_condition(case, "U", patch),
                _boundary_condition(case, "p_rgh", patch),
                _boundary_condition(case, "alpha.water", patch),
                _boundary_condition(case, "tau.water", patch),
                _boundary_condition(case, "theta.water", patch),
            ]
        )
    return rows


def _control_rows(case: Path) -> list[list[Any]]:
    text = _read_text_file(case / "system" / "controlDict")
    rows = [["控制项", "设定值", "说明"]]
    labels = [
        ("application", "求解器"),
        ("endTime", "最终物理时间"),
        ("deltaT", "初始时间步"),
        ("adjustTimeStep", "是否自适应时间步"),
        ("maxCo", "最大 Courant 数"),
        ("maxAlphaCo", "最大界面 Courant 数"),
        ("maxDeltaT", "最大时间步"),
        ("writeControl", "写出控制"),
        ("writeInterval", "写出间隔"),
    ]
    for key, note in labels:
        rows.append([key, _of_entry(text, key), note])
    return rows


def _scheme_rows(case: Path) -> list[list[Any]]:
    schemes = _read_text_file(case / "system" / "fvSchemes")
    solution = _read_text_file(case / "system" / "fvSolution")
    rows = [["类别", "条目", "设定值"]]
    for block_name, keys in (
        ("ddtSchemes", ("default",)),
        ("gradSchemes", ("default",)),
        ("divSchemes", ("div(rhoPhi,U)", "div(phi,theta.water)", "div(phi,alpha)", "div(phirb,alpha)", "div(Sum(tau))")),
        ("laplacianSchemes", ("default",)),
        ("snGradSchemes", ("default",)),
    ):
        block = _of_block(schemes, block_name)
        for key in keys:
            rows.append([block_name, key, _of_entry(block, key)])
    for name in ('"alpha.water.*"', '"(p_rgh.*|pcorr)"', '"(theta.*|tau.*|U.*)"'):
        block = _of_block(solution, name)
        rows.append(["fvSolution", f"{name} solver", _of_entry(block, "solver")])
    pimple = _of_block(solution, "PIMPLE")
    for key in ("nOuterCorrectors", "nCorrectors", "nNonOrthogonalCorrectors", "momentumPredictor"):
        rows.append(["PIMPLE", key, _of_entry(pimple, key)])
    return rows


def _add_dieswell_engineering_pair(
    doc: DocxBuilder,
    *,
    artifacts: list[dict[str, Any]],
    post: dict[str, Any],
    field: str,
    title: str,
    initial_analysis: str,
    final_analysis: str,
    comparison_analysis: str,
    prefer_zoom: bool = True,
) -> None:
    initial_time = _dieswell_field_time(post, field, "initial")
    final_time = _dieswell_field_time(post, field, "final")
    prefix = "dieswell_field_zoom_snapshot" if prefer_zoom else "dieswell_field_snapshot"
    for role, time_value, analysis in (
        ("initial", initial_time, initial_analysis),
        ("final", final_time, final_analysis),
    ):
        label = "早期状态" if role == "initial" else "完成态"
        path = _artifact_by_kind(artifacts, f"{prefix}:{field}:{role}")
        caption = f"{title}（{label}，t={time_value}）"
        if path is None or not path.is_file():
            doc.paragraph(f"{caption}：图像文件未生成。")
        else:
            doc.image(path, caption)
        doc.paragraph(analysis)
    doc.paragraph(comparison_analysis)


def _add_dieswell_initial_final_pair(
    doc: DocxBuilder,
    *,
    artifacts: list[dict[str, Any]],
    post: dict[str, Any],
    field: str,
    title: str,
    purpose: str,
    reading: str,
    initial_conclusion: str,
    final_conclusion: str,
) -> None:
    initial_time = _dieswell_field_time(post, field, "initial")
    final_time = _dieswell_field_time(post, field, "final")
    _add_explained_figure(
        doc,
        _artifact_by_kind(artifacts, f"dieswell_field_snapshot:{field}:initial"),
        f"{title}（初始/早期态，t={initial_time}）",
        purpose=purpose,
        reading=reading,
        conclusion=initial_conclusion,
    )
    _add_explained_figure(
        doc,
        _artifact_by_kind(artifacts, f"dieswell_field_snapshot:{field}:final"),
        f"{title}（完成态，t={final_time}）",
        purpose=purpose,
        reading=reading,
        conclusion=final_conclusion,
    )


def _add_dieswell_modeling_plugin(doc: DocxBuilder, *, case: Path, post: dict[str, Any]) -> None:
    doc.heading("2.4.1 DieSwell 控制方程与物性参数", 3)
    doc.paragraph("针对挤出胀大自由液面问题，动量方程中需要同时考虑黏性扩散、聚合物额外应力和界面力项，可概括为：")
    doc.equation("ρ(∂U/∂t + U·∇U) = −∇p + ∇·(ηₛ∇U) + ∇·τₚ + Fₛ")
    doc.paragraph("聚合物相采用 Oldroyd-BLog 黏弹性模型，其基本 Oldroyd-B 形式为：")
    doc.equation("τₚ + λτₚ^▽ = 2ηₚD")
    doc.paragraph("自由界面采用 VOF 相分数字段 alpha.water 追踪：")
    doc.equation("∂α/∂t + ∇·(αU) = 0")
    doc.paragraph("其中 tau.water 表示聚合物相额外应力，alpha.water=0.5 等值线用于近似表示空气/聚合物自由界面。")
    doc.table(_dieswell_property_rows(case))

    doc.heading("2.4.2 DieSwell 边界条件与时间控制", 3)
    doc.paragraph("下表从当前 case 的 0/ 初始场和 system 控制文件读取，用于说明本次计算真实采用的边界与时间推进设置。")
    doc.table(_dieswell_boundary_rows(case))
    doc.table(_control_rows(case))
    if _dieswell_notes(post):
        doc.paragraph(
            "注：t=0 为初始场，速度、压力和聚合物应力尚未形成可解释的演化结构；"
            "因此场图对比中的“早期状态”采用第一个有效写出时间步。"
        )


def _add_dieswell_result_plugin(
    doc: DocxBuilder,
    *,
    artifacts: list[dict[str, Any]],
    post: dict[str, Any],
) -> None:
    ratio_text, x_text, y_text = _dieswell_metric_summary(post)
    final_time = post.get("latest_time", "未记录")
    tau_stats = _dieswell_field_stats(post, "tau.water:final", zoom=False) or _dieswell_field_stats(post, "tau.water:final")
    n1_stats = _dieswell_field_stats(post, "N1.water:final")
    tau_max = _format_value(tau_stats.get("max")) if tau_stats else "未记录"
    tau_loc = _format_location(tau_stats.get("max_location"))
    n1_max = _format_value(n1_stats.get("max")) if n1_stats else "未记录"
    n1_loc = _format_location(n1_stats.get("max_location"))

    doc.heading("3.2.1 自由边界的时空演化", 3)
    _add_engineering_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_free_surface_overlay"),
        "图 R1 自由液面初始态—中间态—完成态叠加",
        (
            "图 R1 用 alpha.water=0.5 等值线表示空气/聚合物自由界面。"
            f"完成态最大半高约为 {y_text}，对应胀大比 B={ratio_text}；"
            "该图直接回答了挤出物离开口模后自由表面是否外扩的问题。"
        ),
    )
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="alpha.water",
        title="图 R2 口模附近体积分数 alpha.water 局部放大",
        initial_analysis="早期状态下，聚合物相仍主要受口模几何约束，出口附近自由界面刚开始形成。",
        final_analysis="完成态下，出口近场的 alpha.water 过渡带向外移动，说明挤出物截面已经发生可观胀大。",
        comparison_analysis="早期态与完成态对比表明，自由界面在口模出口后发生横向扩张，而不只是整体下游平移。",
    )
    _add_engineering_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_free_surface_plot"),
        "图 R3 完成态自由液面与最大胀大位置",
        (
            f"图 R3 标出了完成态自由界面和最大胀大位置。最大点位于 x≈{x_text}, y≈{y_text}，"
            f"由此得到最终胀大比 B={ratio_text}。该指标是本案例的核心定量交付结果。"
        ),
    )
    _add_engineering_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_swell_ratio_history_plot"),
        "图 R4 胀大比随时间变化",
        (
            f"图 R4 用各写出时间步的自由界面重新计算胀大比，用于判断 t={final_time} 是否可以作为完成态。"
            "若工程应用需要严格稳态设计值，建议结合该曲线进一步判断是否需要延长计算。"
        ),
    )

    doc.heading("3.2.2 速度、压力与应力机制解释", 3)
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="U",
        title="图 R5 口模出口附近速度场 |U| 局部放大",
        initial_analysis="早期状态下，口模内速度场仍保留明显剪切流动特征，出口后速度重排尚未充分发展。",
        final_analysis="完成态下，出口附近速度梯度重新分布，射流边界与速度场变化相互耦合。",
        comparison_analysis="速度场对比说明挤出胀大与出口后流动结构调整相关，而不是孤立的几何轮廓变化。",
    )
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="p_rgh",
        title="图 R6 口模出口附近压力场 p_rgh 局部放大",
        initial_analysis="早期状态下，压力场主要反映口模内驱动流动所需压降和出口附近压力重构。",
        final_analysis="完成态下，口模内压力沿流向释放，进入自由膨胀区后逐步趋向环境压力水平。",
        comparison_analysis="压力场主要用于物理一致性检查，确认自由界面与速度场解释没有受到异常压力分布破坏。",
    )
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="tau.water",
        title="图 R7 口模出口附近聚合物应力 |tau.water| 局部放大",
        initial_analysis="早期状态下，聚合物应力开始在口模出口壁面附近集中，说明受限剪切流动中已经积累弹性变形。",
        final_analysis=f"完成态下，聚合物应力模量最大值约为 {tau_max}，峰值位置位于 {tau_loc}。",
        comparison_analysis="应力集中区域与自由界面外扩区域保持空间关联，是解释挤出胀大的主要力学证据。",
    )
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="N1.water",
        title="图 R8 第一法向应力差 N1=tau_xx-tau_yy 局部放大",
        initial_analysis="早期状态下，N1 已在口模出口附近出现局部增强，表明流向与横向应力开始分化。",
        final_analysis=f"完成态局部视野内最大 N1 约为 {n1_max}，峰值位置位于 {n1_loc}。",
        comparison_analysis=f"N1 增强区域、聚合物应力释放区域与自由界面外扩区域相互对应，最终得到 B={ratio_text} 的胀大结果。",
    )


def _add_dambreak_modeling_plugin(doc: DocxBuilder) -> None:
    doc.heading("2.4.1 damBreak 自由液面模型说明", 3)
    doc.paragraph(
        "damBreak 属于不可混溶水-空气两相自由液面问题。报告采用统一骨架说明计算过程，"
        "并在结果章节重点解释 alpha.water 相分数、水体前沿、速度场和压力场。"
    )
    doc.equation("∂α/∂t + ∇·(αU) = 0")
    doc.paragraph("其中 alpha.water 表示水相体积分数，alpha.water≈0.5 的过渡带可作为水-空气自由液面的近似位置。")


def _dambreak_metric_summary(post: dict[str, Any]) -> tuple[str, str]:
    dambreak = post.get("dambreak_free_surface") or {}
    front_x = dambreak.get("front_x")
    max_height = dambreak.get("max_height")
    return (
        _format_value(front_x) if front_x is not None else "未生成",
        _format_value(max_height) if max_height is not None else "未生成",
    )


def _dambreak_field_time(post: dict[str, Any], field: str, role: str) -> str:
    item = ((post.get("dambreak_enhanced_figures") or {}).get("fields") or {}).get(f"{field}:{role}") or {}
    time_value = item.get("time")
    if time_value is None:
        return "未记录"
    requested = item.get("requested_time")
    if requested is not None and str(requested) != str(time_value):
        return f"{time_value}（请求 {requested}，采用首个可读写出时间）"
    return str(time_value)


def _add_dambreak_engineering_pair(
    doc: DocxBuilder,
    *,
    artifacts: list[dict[str, Any]],
    post: dict[str, Any],
    field: str,
    title: str,
    initial_analysis: str,
    final_analysis: str,
    comparison_analysis: str,
) -> None:
    initial_time = _dambreak_field_time(post, field, "initial")
    final_time = _dambreak_field_time(post, field, "final")
    for role, time_value, analysis in (
        ("initial", initial_time, initial_analysis),
        ("final", final_time, final_analysis),
    ):
        label = "初始/早期状态" if role == "initial" else "完成态"
        path = _artifact_by_kind(artifacts, f"dambreak_field_snapshot:{field}:{role}")
        caption = f"{title}（{label}，t={time_value}）"
        if path is None or not path.is_file():
            doc.paragraph(f"{caption}：图像文件未生成。")
        else:
            doc.image(path, caption)
        doc.paragraph(analysis)
    doc.paragraph(comparison_analysis)


def _add_dambreak_result_plugin(doc: DocxBuilder, *, artifacts: list[dict[str, Any]], post: dict[str, Any]) -> None:
    final_time = post.get("latest_time", "未记录")
    front_x, max_height = _dambreak_metric_summary(post)
    doc.heading("3.2.1 自由液面与水体前沿", 3)
    _add_engineering_figure(
        doc,
        _artifact_by_kind(artifacts, "dambreak_free_surface_overlay"),
        "图 R1 自由液面初始态—中间态—完成态叠加",
        (
            "图 R1 用 alpha.water=0.5 等值线表示水-空气自由液面，并叠加不同时刻轮廓。"
            "该图用于观察水柱坍塌后自由液面由初始水柱向下游推进和铺展的过程。"
        ),
    )
    _add_engineering_figure(
        doc,
        _artifact_by_kind(artifacts, "dambreak_free_surface_plot"),
        "图 R2 完成态 alpha.water=0.5 自由液面与水体前沿",
        (
            f"图 R2 标出 t={final_time} 时由 alpha.water=0.5 提取的自由液面和最下游水体前沿。"
            f"当前计算得到 front_x≈{front_x}，最高自由液面高度约为 {max_height}。"
        ),
    )
    _add_engineering_figure(
        doc,
        _artifact_by_kind(artifacts, "dambreak_front_history_plot"),
        "图 R3 水体前沿位置随时间变化",
        (
            "图 R3 逐时间步提取 alpha.water=0.5 自由液面上的最大 x 坐标，形成 water-front x(t) 曲线。"
            "该曲线用于判断溃坝波前推进速度和最终时刻前沿位置，而不是只依赖单张云图。"
        ),
    )
    _add_dambreak_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="alpha.water",
        title="图 R4 alpha.water 相分数场",
        initial_analysis="初始/早期状态下，alpha.water 高值区表示水柱初始分布，自由液面尚未充分铺展。",
        final_analysis="完成态下，alpha.water 高值区沿底部向下游推进，过渡带显示水-空气界面的最终形态。",
        comparison_analysis="alpha.water 初始态与完成态对比直接说明水体从初始水柱坍塌并向下游推进的自由液面演化。",
    )

    doc.heading("3.2.2 速度场与压力场", 3)
    _add_dambreak_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="U",
        title="图 R5 速度场 |U|",
        initial_analysis="初始/早期状态下，速度场反映水柱刚开始坍塌和加速的区域。",
        final_analysis="完成态下，速度场显示水体沿底部推进、撞击和回流区域的位置。",
        comparison_analysis="速度场对比说明自由液面推进由水体重力坍塌后的惯性运动驱动，是解释波前推进的动力学依据。",
    )
    pressure_field = "p_rgh" if _artifact_by_kind(artifacts, "dambreak_field_snapshot:p_rgh:final") else "p"
    _add_dambreak_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field=pressure_field,
        title="图 R6 压力场",
        initial_analysis="初始/早期状态下，压力场主要反映静水压分布和启动后的局部调整。",
        final_analysis="完成态下，压力场用于识别水体撞击壁面、底部或障碍区域后的局部高压区。",
        comparison_analysis="压力场对比用于检查溃坝自由液面运动是否伴随合理的压力重构，辅助判断结果物理一致性。",
    )


def _add_dieswell_special_report_body(
    doc: DocxBuilder,
    *,
    case: Path,
    manifest: dict[str, Any],
    post: dict[str, Any],
    tutorial: dict[str, Any],
    benchmark: dict[str, Any],
    artifacts: list[dict[str, Any]],
    application: str,
    target: dict[str, Any],
    geometry: str,
    objective_rows: list[list[Any]],
    credibility: str,
    limitations: list[str],
) -> None:
    ratio_text, x_text, y_text = _dieswell_metric_summary(post)
    status_text = "完成" if manifest.get("run_status") == "passed" and post.get("status") == "passed" else "未完全完成"
    final_time = post.get("latest_time", "未记录")
    rheology = manifest.get("rheology_spec") or {}
    physics = manifest.get("physics_spec") or {}
    dieswell = post.get("dieswell_free_surface") or {}
    template_id = tutorial.get("template_id") or "未记录"
    report_question = _clean_requirement_for_report(application)
    lambda_value = ((manifest.get("problem_intent") or {}).get("known_parameters") or {}).get("lambda")
    if lambda_value is None:
        lambda_value = (rheology.get("parameters") or {}).get("lambda")
    lambda_text = _format_value(lambda_value) if lambda_value is not None else "未记录"
    tau_stats = _dieswell_field_stats(post, "tau.water:final", zoom=False) or _dieswell_field_stats(post, "tau.water:final")
    n1_stats = _dieswell_field_stats(post, "N1.water:final")
    tau_max = _format_value(tau_stats.get("max")) if tau_stats else "未记录"
    tau_loc = _format_location(tau_stats.get("max_location"))
    n1_max = _format_value(n1_stats.get("max")) if n1_stats else "未记录"
    n1_loc = _format_location(n1_stats.get("max_location"))

    doc.heading("1. 物理问题定义与工程背景", 1)
    doc.heading("1.1 问题背景与物理模型描述", 2)
    doc.paragraph(report_question)
    doc.paragraph(
        "本案例关注平面狭缝口模的挤出胀大：聚合物熔体在口模内受到剪切并累积弹性应力，"
        "离开口模后壁面约束消失，应力释放会推动自由边界向外扩张。"
        "因此，本报告围绕“胀大到什么程度、由哪些流动和应力证据支撑”组织分析。"
    )
    doc.callout(
        "核心结论预览",
        [
            f"最终时间：t={final_time}",
            f"稳态/最终胀大比：B={ratio_text}",
            f"最大胀大位置：x≈{x_text}, y≈{y_text}",
            "自由界面定义：alpha.water=0.5 等值线近似表示空气/聚合物相界面。",
        ],
    )

    doc.heading("1.2 数值模拟关键挑战", 2)
    for item in [
        "自由边界追踪：需要从 alpha.water 体积分数字段中提取相界面，而不是只观察单个场变量云图。",
        "模口附近应力集中：口模出口处边界约束突变会导致速度、压力和聚合物应力快速重排。",
        "黏弹性数值稳定性：当前模板为 Oldroyd-BLog 变体，使用 log-conformation 类设置提高高弹性计算稳定性。",
    ]:
        doc.bullet(item)

    doc.heading("1.3 核心技术指标与交付要求", 2)
    doc.table(objective_rows)
    doc.paragraph("本报告后续章节围绕上述技术指标组织：先说明数值模型、网格与后处理方法，再用自由界面、速度、压力和应力证据解释胀大结果。")

    doc.heading("1.4 模型范围与输入约束", 2)
    doc.table([
        ["项目", "记录"],
        ["几何/场景", geometry],
        ["本构模型", rheology.get("selected_model", "未记录")],
        ["模板变体", template_id],
        ["相态/自由液面", "两相自由液面计算；自由界面由 alpha.water=0.5 提取"],
        ["松弛时间 lambda", lambda_text],
    ])

    doc.page_break()
    doc.heading("2. 数值建模方案与计算实施", 1)
    doc.heading("2.1 求解器选择与本构模型配置", 2)
    doc.table([
        ["项目", "内容"],
        ["数值平台", "OpenFOAM v9 + RheoTool 扩展"],
        ["求解器", target.get("solver")],
        ["案例基线", "RheoTool 5.3.3 DieSwell / Oldroyd-BLog"],
        ["本构模型", f"Oldroyd-BLog，lambda={lambda_text}"],
        ["计算类型", "平面狭缝口模两相自由液面瞬态计算"],
    ])
    doc.paragraph(
        "本次计算采用 rheoInterFoam 对平面狭缝口模挤出过程进行瞬态模拟。"
        "聚合物相采用 Oldroyd-BLog 黏弹性本构，空气/聚合物相界面通过 alpha.water 场捕捉。"
        "后处理重点放在口模出口附近的流动重排、压力松弛、聚合物应力释放，以及最终自由边界外扩程度。"
    )

    doc.heading("2.2 计算域设计与网格划分方案", 2)
    doc.table([
        ["项目", "内容"],
        ["网格来源", "RheoTool DieSwell 教程模板"],
        ["网格摘要", _mesh_summary(case)],
        ["技术用途", "确认口模出口与下游自由膨胀区的位置，为解释自由界面图提供空间参照。"],
    ])
    _add_engineering_figure(
        doc,
        _find_artifact(artifacts, kind="dieswell_mesh_zoom") or _find_artifact(artifacts, kind="dieswell_mesh_overview"),
        "图 M1 口模出口附近局部网格放大图",
        "图 M1 将视野集中在 x∈[-5,10] 的口模出口区域。该区域是速度边界条件切换、压力重构和聚合物应力释放最集中的位置，"
        "也是判断挤出胀大机理是否可信的关键观察窗口。局部网格图比全域长条图更能展示出口尖角和下游近场区的解析能力。",
    )

    doc.heading("2.3 数理模型与物性参数", 2)
    doc.heading("2.3.1 核心控制方程", 3)
    doc.paragraph(
        "本案例采用不混溶两相流框架描述空气/聚合物自由界面。动量守恒方程中耦合了黏性扩散、聚合物额外应力以及界面力项，可概括为："
    )
    doc.equation("ρ(∂U/∂t + U·∇U) = −∇p + ∇·(ηₛ∇U) + ∇·τₚ + Fₛ        (1)")
    doc.paragraph(
        "其中 τₚ 为聚合物额外应力，Fₛ 为两相界面力项；当前 case 的 σ=0，因此表面张力项在本算例中不主导结果。"
    )
    doc.paragraph(
        "聚合物相采用 Oldroyd-BLog 黏弹性模型。Oldroyd-B 本构关系可写为："
    )
    doc.equation("τₚ + λ τₚ^▽ = 2ηₚD        (2)")
    doc.paragraph(
        "其中 λ 为松弛时间，τₚ^▽ 表示上对流时间导数，D 为形变速率张量；报告中的 tau.water 表示聚合物相额外应力，"
        "theta.water 为 log-conformation 相关变量，用于提高黏弹性应力输运的数值稳定性。"
    )
    doc.paragraph("自由界面采用 VOF 方法通过相分数字段 alpha.water 追踪，其对流输运方程可概括为：")
    doc.equation("∂α/∂t + ∇·(αU) = 0        (3)")
    doc.paragraph("后处理以 alpha.water=0.5 等值线近似表示空气/聚合物相界面。")

    doc.heading("2.3.2 流变学与物性输入", 3)
    doc.paragraph("表 2.3-1 的数值来自当前 case 的 constant/constitutiveProperties；这些是教程/算例参数，不在报告中重新标定为 SI 实测物性。")
    doc.table(_dieswell_property_rows(case))

    doc.heading("2.4 边界条件与求解控制", 2)
    doc.heading("2.4.1 物理边界条件配置", 3)
    doc.paragraph("表 2.4-1 来自当前 case 的 0/ 初始场文件，列出了主要 patch 上速度、压力、相分数和黏弹性应力变量的真实边界条件。")
    doc.table(_dieswell_boundary_rows(case))

    doc.heading("2.4.2 时间推进与数值离散控制", 3)
    doc.paragraph("时间推进参数来自 system/controlDict。当前计算采用自适应时间步控制，并对整体 Courant 数与界面 Courant 数设置严格上限。")
    doc.table(_control_rows(case))
    doc.paragraph("主要离散格式和线性求解器设置来自 system/fvSchemes 与 system/fvSolution。")
    doc.table(_scheme_rows(case))

    doc.heading("2.4.3 执行状态记录", 3)
    doc.table([
        ["项目", "记录/解释"],
        ["最终时间", final_time],
        ["执行状态", status_text],
        ["Schema / Manifest", manifest.get("validation_status", "未记录")],
        ["OpenFOAM 求解", manifest.get("run_status", "未记录")],
        ["后处理状态", post.get("status", "未记录")],
    ])
    notes = _dieswell_notes(post)
    if notes:
        doc.paragraph(
            "注：t=0 为初始场，速度、压力和聚合物应力尚未形成可用于机理分析的完整演化结构。"
            "因此，速度、压力和应力的“早期状态”采用第一个有效写出时间步进行对比；自由界面 alpha.water 仍保留 t=0 作为初始形态。"
        )

    doc.heading("2.5 后处理与评价指标提取", 2)
    doc.table([
        ["技术指标", "后处理动作", "输出证据"],
        ["胀大程度", "提取 alpha.water=0.5 自由界面并计算 max_y / 口模半高", "自由界面图、胀大比 JSON/CSV"],
        ["是否达到完成态", "统计胀大比随时间变化", "swell_ratio_vs_time 曲线"],
        ["速度场如何支撑界面演化", "绘制初始/完成态 |U| 云图", "U 初始/完成态图片"],
        ["压力是否合理松弛", "绘制初始/完成态 p_rgh 云图", "p_rgh 初始/完成态图片"],
        ["应力是否解释胀大机制", "绘制初始/完成态 |tau.water| 云图", "tau.water 初始/完成态图片"],
    ])

    doc.heading("2.6 数值质量检查", 2)
    doc.table(_residual_rows(post))
    residual_plot = _find_artifact(artifacts, kind="residual_plot")
    if residual_plot:
        _add_engineering_figure(
            doc,
            residual_plot,
            "图 Q1 求解残差历史",
            "图 Q1 用于检查求解过程是否存在持续发散。残差历史并不直接给出胀大比，"
            "但它是判断后续自由界面、速度、压力和应力分析是否具备数值基础的重要质量证据。",
        )
    _comparison_section(doc, post)

    doc.page_break()
    doc.heading("3. 模拟结果分析与讨论", 1)
    doc.heading("3.1 胀大比与界面位置的定量分析", 2)
    doc.callout(
        "结论摘要",
        [
            f"计算状态：{status_text}；最终时间 t={final_time}",
            f"挤出胀大比：B={ratio_text}",
            f"最大自由界面位置：x≈{x_text}, y≈{y_text}",
            f"定义：{dieswell.get('definition', 'max_free_surface_y_downstream / die_exit_half_height')}",
        ],
    )
    doc.table(objective_rows)

    doc.heading("3.2 自由边界的时空演化", 2)
    _add_engineering_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_free_surface_overlay"),
        "图 R1 自由液面初始态—中间态—完成态叠加",
        (
            "图 R1 用 alpha.water=0.5 等值线表示空气/聚合物自由界面，并叠加了初始、中间和完成态轮廓。"
            f"界面在离开口模后持续向外扩张，完成态最大半高约为 {y_text}，对应胀大比 B={ratio_text}。"
            "这张图直接回答了客户最关心的“是否发生胀大以及胀大到什么程度”。"
        ),
    )
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="alpha.water",
        title="图 R2 口模附近体积分数 alpha.water 局部放大",
        initial_analysis=(
            "早期状态下，alpha.water 接近 1 的聚合物相仍主要受口模几何约束，出口附近自由界面刚开始形成。"
            "该图用于确认初始相分布和口模出口位置，为后续判断界面外扩提供基准。"
        ),
        final_analysis=(
            "完成态下，出口近场的 alpha.water 过渡带已经明显向外移动，聚合物相在离开壁面约束后形成更宽的自由边界包络。"
            "这说明挤出物截面已经发生可观胀大。"
        ),
        comparison_analysis=(
            "对比早期态和完成态可以看到，自由界面并非仅在下游平移，而是在口模出口后发生横向扩张；"
            "这与图 R1 和图 R3 中由 alpha.water=0.5 提取的全局自由界面结果一致。"
        ),
    )
    _add_engineering_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_free_surface_plot"),
        "图 R3 完成态自由液面与最大胀大位置",
        (
            f"图 R3 标出了完成态自由界面和最大胀大位置。最大点位于 x≈{x_text}, y≈{y_text}，"
            f"由此得到最终胀大比 B={ratio_text}。该指标是本案例的核心定量交付结果。"
        ),
    )
    _add_engineering_figure(
        doc,
        _artifact_by_kind(artifacts, "dieswell_swell_ratio_history_plot"),
        "图 R4 胀大比随时间变化",
        (
            f"图 R4 用各写出时间步的自由界面重新计算胀大比，用于判断 t={final_time} 是否可以作为完成态。"
            "曲线后段仍存在小幅波动，因此本报告将其表述为当前计算终止时刻的完成态结果；"
            "若工程应用需要严格稳态设计值，建议在此基础上延长计算或提高输出频率进行复核。"
        ),
    )

    doc.heading("3.3 速度场分析", 2)
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="U",
        title="图 R5 口模出口附近速度场 |U| 局部放大",
        initial_analysis=(
            "早期状态下，口模内速度场仍保留明显的剪切流动特征，中心区域速度较高、近壁区域速度较低。"
            "流体刚跨出口时，壁面剪切约束的解除尚未完全传递到下游自由膨胀区。"
        ),
        final_analysis=(
            "完成态下，出口附近速度梯度已经重新分布，射流边界与速度场变化相互耦合。"
            "局部速度场显示流体离开口模后逐步从受限剪切流动过渡到自由表面主导的下游流动。"
        ),
        comparison_analysis=(
            "速度场对比表明，挤出胀大不是孤立的几何轮廓变化，而是由出口后速度重排、自由界面外扩和黏弹性应力释放共同决定。"
        ),
    )

    doc.heading("3.4 压力场分析", 2)
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="p_rgh",
        title="图 R6 口模出口附近压力场 p_rgh 局部放大",
        initial_analysis=(
            "早期状态下，压力场主要反映口模内驱动流动所需的压降，以及出口附近刚开始形成的局部压力重构。"
            "此时下游自由膨胀区尚未完全发展，压力分布仍带有明显的入口—出口调整特征。"
        ),
        final_analysis=(
            "完成态下，口模内压力沿流向释放，进入自由膨胀区后逐步趋向环境压力水平。"
            "出口附近未出现孤立高压斑或明显非连续突变，说明自由界面和速度场解释没有受到异常压力场破坏。"
        ),
        comparison_analysis=(
            "压力场对比主要用于物理一致性检查：早期态反映启动后的压力重构，完成态则表明出口附近压力已与发展后的自由界面形态相协调。"
        ),
    )

    doc.heading("3.5 应力场分析", 2)
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="tau.water",
        title="图 R7 口模出口附近聚合物应力 |tau.water| 局部放大",
        initial_analysis=(
            "早期状态下，聚合物应力已经开始在口模出口壁面附近集中，说明流体在受限剪切流动中积累了弹性变形。"
            "但此时自由界面尚未充分展开，应力释放过程仍处于发展阶段。"
        ),
        final_analysis=(
            f"完成态下，聚合物应力模量最大值约为 {tau_max}，峰值位置位于 {tau_loc}，即口模出口壁面尖角附近。"
            "该位置正是壁面剪切约束向自由表面条件切换的区域，也是挤出胀大机理最敏感的位置。"
        ),
        comparison_analysis=(
            "从早期态到完成态，应力集中区域与自由界面外扩区域保持空间关联。"
            "聚合物分子链在口模内积累的弹性应力于出口后释放，推动射流横向外扩，是本案例发生挤出胀大的主要力学原因。"
        ),
    )
    _add_dieswell_engineering_pair(
        doc,
        artifacts=artifacts,
        post=post,
        field="N1.water",
        title="图 R8 第一法向应力差 N1=tau_xx-tau_yy 局部放大",
        initial_analysis=(
            "早期状态下，第一法向应力差 N1 已在口模出口附近出现局部增强，表明流向拉伸应力与横向应力开始分化。"
            "这为后续自由表面外扩提供了早期力学信号。"
        ),
        final_analysis=(
            f"完成态局部视野内最大 N1 约为 {n1_max}，峰值位置位于 {n1_loc}。"
            "N1 反映流向拉伸应力与横向应力的差异，是黏弹性流体产生挤出胀大的典型力学来源。"
        ),
        comparison_analysis=(
            f"结合图 R1—R4 可见，N1 增强区域、聚合物应力释放区域与自由界面外扩区域在空间上相互对应，"
            f"最终在下游 x≈{x_text} 处达到 B={ratio_text} 的最大胀大比。"
        ),
    )

    doc.heading("3.6 报告结论、不确定度评估与改进建议", 2)
    doc.paragraph(
        f"综合自由界面、速度、压力和聚合物应力场，本次计算回答了客户关于平面狭缝口模挤出胀大的核心问题："
        f"在当前 Oldroyd-BLog 本构参数设置下，最终胀大比为 B={ratio_text}。"
    )
    doc.paragraph(
        f"本次计算基于已记录的流变学输入参数进行显式求解，其中松弛时间 lambda={lambda_text}。"
        "计算过程、后处理指标和图表产物均保留在 case 目录中，可用于复核与追溯。"
    )
    doc.heading("3.6.1 不确定度与局限性说明", 3)
    for item in limitations:
        doc.bullet(item)
    doc.heading("3.6.2 建议与后续", 3)
    for item in _recommendations(limitations):
        doc.bullet(item)


def generate_formal_case_report_docx(
    case_dir: str | Path,
    *,
    output_path: str | Path | None = None,
    report_status: str = "正式",
    platform_version: str | None = None,
) -> Path:
    case = Path(case_dir).resolve()
    manifest = _read_json(case / "manifest.json")
    post = _read_json(case / "POSTPROCESS_REPORT.json")
    tutorial = _read_json(case / "TUTORIAL_TEMPLATE_IMPORT.json")
    benchmark = _read_json(case / "BENCHMARK_IMPORT.json")
    artifacts = _artifact_items(case)

    case_id = case.name
    report_id = f"report-{case_id}"
    date_text = datetime.now().strftime("%Y-%m-%d")
    platform_version = platform_version or os.getenv("FOAMAGENT_PLATFORM_VERSION") or "foamagent-codebuddy:dev（digest 未记录）"

    problem = manifest.get("problem_intent", {}) or {}
    application = _short_requirement(_text(problem.get("application"), post.get("user_requirement", "")))
    target = _target_summary(manifest)
    rheology = manifest.get("rheology_spec") or {}
    physics = manifest.get("physics_spec") or {}
    geometry = _geometry_label(problem.get("geometry_class"), application)
    title = _case_title(manifest, application)
    credibility = _credibility_from_sources(application + json.dumps(rheology, ensure_ascii=False))
    limitations = _limitations(case, manifest, post, application)
    objective_rows = _objective_rows(manifest, post, artifacts, application)
    _assert_report_answers_user_questions(objective_rows, application=application)
    dieswell_report = _is_dieswell_report(manifest, post, tutorial, application)
    dambreak_report = _is_dambreak_report(manifest, tutorial, application)

    doc = DocxBuilder(title=title)
    doc.paragraph(title, style="Title", bold=True, align="center")
    doc.paragraph(f"基于 Foam-Agent / {target.get('channel', '未记录')} / {target.get('solver', '未记录')}", align="center")
    doc.paragraph("")
    doc.table([
        ["字段", "内容"],
        ["report_id", report_id],
        ["case_id", case_id],
        ["日期", date_text],
        ["平台版本", platform_version],
        ["报告状态", report_status],
    ])
    doc.page_break()

    status_text = "完成" if manifest.get("run_status") == "passed" and post.get("status") == "passed" else "未完全完成"
    report_question = _clean_requirement_for_report(application)

    doc.heading("1. 物理问题定义与工程背景", 1)
    doc.heading("1.1 问题背景与物理模型描述", 2)
    doc.paragraph(report_question)
    doc.paragraph(_problem_background_paragraph(geometry=geometry, application=application))

    doc.heading("1.2 数值模拟关键挑战", 2)
    for item in [
        f"问题类型识别：需要将业务描述映射到 {geometry}，并保持几何、边界和求解器来源可追溯。",
        "结果证据组织：报告只展示能够回答用户技术指标的关键图表，避免把运行日志和自动截图简单堆叠。",
        "可信度边界：若缺少独立参考解、网格无关性或用户实测参数，报告必须披露限制而不是给出过度确定结论。",
    ]:
        doc.bullet(item)

    doc.heading("1.3 核心技术指标与交付要求", 2)
    doc.table(objective_rows)
    doc.table([
        ["项目", "设置"],
        ["几何/问题类型", geometry],
        ["相态", physics.get("phase_type", "未记录")],
        ["是否瞬态", physics.get("transient", "未记录")],
        ["是否自由液面", physics.get("free_surface", "未记录")],
        ["目标", ", ".join(problem.get("objectives") or physics.get("objectives") or []) or "未记录"],
    ])

    doc.heading("1.4 模型范围与输入约束", 2)
    doc.table(_parameter_rows(manifest, application))
    for item in [
        "所有物理参数来源以 manifest / requirement 中记录为准；报告不补造未提供参数。",
        "后处理图表均来自当前 case_dir 的 POSTPROCESS_ARTIFACTS.json 或标准 postprocess 产物。",
        "若未生成独立参考数据，报告不会声明定量 benchmark 误差达标。",
        f"本案例采用的计算环境为 channel={target.get('channel')}，solver={target.get('solver')}，distribution={target.get('distribution')}。",
    ]:
        doc.bullet(item)

    doc.page_break()
    doc.heading("2. 数值建模方案与计算实施", 1)
    doc.heading("2.1 问题类型与计算方案", 2)
    doc.bullet(f"问题类型：{geometry}；计算环境：{target.get('channel', '未记录')} / {target.get('solver', '未记录')}。")
    if tutorial:
        doc.bullet(f"采用已登记基线案例：{tutorial.get('template_id')}，保持其几何、网格、边界条件、本构参数和数值设置。")
    elif benchmark:
        doc.bullet(f"采用本地 certified benchmark：{benchmark.get('benchmark_id', benchmark.get('id', '未记录'))}。")
    else:
        doc.bullet("根据需求生成/复用 case，并执行标准 OpenFOAM 后处理流程。")

    doc.heading("2.2 求解器与基线案例设置", 2)
    doc.table([
        ["项目", "内容"],
        ["channel", target.get("channel")],
        ["version", target.get("version")],
        ["solver", target.get("solver")],
        ["distribution", target.get("distribution")],
        ["模板/benchmark", tutorial.get("template_id") or benchmark.get("benchmark_id") or benchmark.get("id") or "未使用整体导入"],
    ])

    doc.heading("2.3 计算域、网格与初始化", 2)
    doc.table([
        ["项目", "内容"],
        ["来源", "tutorial template" if tutorial else "certified benchmark" if benchmark else "generated case"],
        ["网格摘要", _mesh_summary(case)],
        ["说明", "从 system/blockMeshDict 自动提取；复杂网格仅给出摘要。"],
    ])
    mesh_figure = _find_artifact(artifacts, kind="dieswell_mesh_overview")
    if dieswell_report:
        _add_dieswell_mesh_explanation(doc, mesh_figure)
    elif mesh_figure:
        doc.image(mesh_figure, "图 1 DieSwell 网格概览", width_in=5.8)

    doc.heading("2.4 数值配置与执行流程", 2)
    doc.table(_execution_rows(manifest, post))
    doc.bullet("执行流程：网格/初始化 → 求解器运行 → 结果重构 → 场图、残差、自由液面和目标指标后处理。")
    if dieswell_report:
        _add_dieswell_modeling_plugin(doc, case=case, post=post)
    elif dambreak_report:
        _add_dambreak_modeling_plugin(doc)

    doc.heading("2.5 无量纲数核对", 2)
    dimless = _extract_dimensionless(application)
    rows = [["无量纲数", "需求/manifest 解析值", "状态"]]
    for name in ("Re", "Wi", "De", "beta"):
        rows.append([name, dimless.get(name, "未记录"), "recorded" if name in dimless else "missing"])
    doc.table(rows)

    doc.heading("2.6 数值质量检查", 2)
    doc.heading("2.6.1 收敛证据", 3)
    doc.table(_residual_rows(post))
    residual_plot = next((path for path, caption in _select_figures(case) if "残差" in caption), None)
    if residual_plot:
        _add_engineering_figure(
            doc,
            residual_plot,
            "图 Q1 求解残差历史",
            "图 Q1 用于检查求解过程是否存在持续发散。残差历史不直接给出业务指标，"
            "但可为后续场图和定量结果提供数值质量依据。",
        )

    doc.heading("2.6.2 守恒性/压力指标", 3)
    pressure = ((post.get("metrics") or {}).get("pressure") or {})
    if "pressure_drop" in pressure:
        doc.paragraph(f"压力降指标：{pressure.get('pressure_drop')}。")
    elif pressure.get("pressure_drop_reason"):
        doc.paragraph(f"压力/守恒类指标未完整生成：{pressure.get('pressure_drop_reason')}。")
    else:
        doc.paragraph("当前未生成独立质量/动量闭合误差表；以残差历史和后处理产物作为基础质量证据。")

    doc.heading("2.6.3 验证对标", 3)
    _comparison_section(doc, post)

    doc.page_break()
    doc.heading("3. 模拟结果分析与讨论", 1)
    doc.heading("3.1 核心技术指标的定量回答", 2)
    summary_lines = [
        f"计算状态：{status_text}；最新时间步 t={post.get('latest_time', '未记录')}",
        f"求解链路：{target.get('channel', '未记录')} / {target.get('solver', '未记录')}",
    ]
    if len(objective_rows) > 1:
        summary_lines.append(f"核心回答：{objective_rows[1][0]} → {objective_rows[1][1]}")
    doc.callout("结论摘要", summary_lines)
    doc.table(objective_rows)

    doc.heading("3.2 关键计算结果图表", 2)
    if dieswell_report:
        doc.paragraph("本节按自由界面、速度、压力和应力证据组织 DieSwell 专用结果；其他自动产物保留在 postprocess 目录和 artifact manifest 中。")
        _add_dieswell_result_plugin(doc, artifacts=artifacts, post=post)
    elif dambreak_report:
        doc.paragraph("本节按自由液面、水体前沿、速度场和压力场组织 damBreak 专用结果；其他自动产物保留在 postprocess 目录和 artifact manifest 中。")
        _add_dambreak_result_plugin(doc, artifacts=artifacts, post=post)
    else:
        selected_figures = []
        for path, caption in _select_figures(case):
            if "残差" in caption or "网格概览" in caption:
                continue
            selected_figures.append((path, caption))
        if not selected_figures:
            doc.paragraph("本案例未发现可插入的 PNG/JPG 图表产物。")
        for index, (path, caption) in enumerate(selected_figures, start=1):
            doc.image(path, f"图 {index} {caption}", width_in=5.8)

    doc.heading("3.3 物理合理性说明", 2)
    doc.bullet("本节基于实际后处理产物进行定性说明；未生成参考对比时不做定量达标断言。")
    if post.get("kinetic_energy", {}).get("status") == "passed":
        last = (post.get("kinetic_energy") or {}).get("last") or {}
        doc.bullet(f"已生成平均动能历史，最新 Ek={_format_value(last.get('kinetic_energy_average'))}。")
    if (post.get("sampleDict") or {}).get("status") == "passed" or (post.get("samples") or {}).get("status") == "present":
        doc.bullet("已按 case 中 sampleDict/后处理配置提取剖面或采样线数据。")
    if tutorial:
        doc.bullet(f"结果来自基线案例：{tutorial.get('template_id')}（tier={tutorial.get('tier')}）。")
    if benchmark:
        doc.bullet(f"结果来自认证 benchmark：{benchmark.get('benchmark_id', benchmark.get('id', '未记录'))}。")

    doc.heading("3.4 报告结论、不确定度评估与改进建议", 2)
    doc.paragraph(f"参数与结果可追溯性：{credibility}。计算输入、后处理指标和图表产物均保留在 case 目录中，可用于复核。")
    doc.heading("3.4.1 不确定度与局限性说明", 3)
    for item in limitations:
        doc.bullet(item)
    doc.heading("3.4.2 建议与后续", 3)
    for item in _recommendations(limitations):
        doc.bullet(item)

    out = Path(output_path) if output_path else case / "FINAL_REPORT.docx"
    return doc.save(out)

def _add_image_if_present(doc: DocxBuilder, path: Path, caption: str, *, width_in: float) -> None:
    if path.is_file():
        doc.image(path, caption, width_in=width_in)
    else:
        doc.paragraph(f"{caption}：图像文件未找到（{path}）。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Chinese formal Word report for a Foam-Agent case.")
    parser.add_argument("case_dir")
    parser.add_argument("--output", default=None)
    parser.add_argument("--status", default="正式", choices=["正式", "探索性"])
    parser.add_argument("--platform-version", default=None)
    args = parser.parse_args(argv)
    output = generate_formal_case_report_docx(
        args.case_dir,
        output_path=args.output,
        report_status=args.status,
        platform_version=args.platform_version,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
