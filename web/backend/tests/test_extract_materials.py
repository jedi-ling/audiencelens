"""/api/extract-materials：PDF/DOCX 真实解析（此前不管什么格式都硬当 UTF-8/GBK 文本
解码，二进制文件必挂——UI 写着支持 pdf/doc/docx，实际全是空头支票）。

覆盖：
  1. .docx 真实生成一份文档（含表格），验证段落+表格文字都被提取出来
  2. .pdf 用 mock 验证解析逻辑接线正确（加密/损坏两种失败态也如实报错，不是 500）
  3. .doc（旧版二进制格式）明确拒绝并指向 .docx，而不是含糊的"无法解析编码"
  4. .txt/.md 等纯文本格式的原有行为不受影响
"""

import io
from unittest.mock import MagicMock, patch

import pytest


def _make_docx_bytes(paragraphs, table_rows=None):
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    if table_rows:
        table = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for i, row in enumerate(table_rows):
            for j, cell_text in enumerate(row):
                table.cell(i, j).text = cell_text
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestDocxExtraction:
    def test_extracts_paragraphs_and_table_cells(self, client):
        content = _make_docx_bytes(
            ["游戏名称：星际拓荒", "核心玩法：太空探索"],
            table_rows=[["字段", "内容"], ["定价", "$29.99"]],
        )
        r = client.post(
            "/api/extract-materials",
            data={"task_type": "concept_review"},
            files={"file": ("concept.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert r.status_code == 200
        body = r.json()
        assert "materials" in body

    def test_corrupt_docx_rejected_cleanly(self, client):
        r = client.post(
            "/api/extract-materials",
            data={"task_type": "concept_review"},
            files={"file": ("broken.docx", b"not a real docx file", "application/octet-stream")},
        )
        assert r.status_code == 400
        assert "损坏" in r.json()["detail"] or "无效" in r.json()["detail"]

    def test_empty_docx_reports_no_text(self, client):
        content = _make_docx_bytes([])
        r = client.post(
            "/api/extract-materials",
            data={"task_type": "concept_review"},
            files={"file": ("empty.docx", content, "application/octet-stream")},
        )
        assert r.status_code == 400
        assert "未提取到文字" in r.json()["detail"]


class TestPdfExtraction:
    def test_extracts_text_from_pages(self, client):
        fake_page1 = MagicMock()
        fake_page1.extract_text.return_value = "第一页内容"
        fake_page2 = MagicMock()
        fake_page2.extract_text.return_value = "第二页内容"
        fake_reader = MagicMock(is_encrypted=False, pages=[fake_page1, fake_page2])

        with patch("pypdf.PdfReader", return_value=fake_reader):
            r = client.post(
                "/api/extract-materials",
                data={"task_type": "concept_review"},
                files={"file": ("doc.pdf", b"%PDF-fake-bytes", "application/pdf")},
            )
        assert r.status_code == 200

    def test_encrypted_pdf_rejected(self, client):
        fake_reader = MagicMock(is_encrypted=True)
        with patch("pypdf.PdfReader", return_value=fake_reader):
            r = client.post(
                "/api/extract-materials",
                data={"task_type": "concept_review"},
                files={"file": ("secret.pdf", b"%PDF-fake-bytes", "application/pdf")},
            )
        assert r.status_code == 400
        assert "加密" in r.json()["detail"]

    def test_corrupt_pdf_rejected(self, client):
        from pypdf.errors import PdfReadError

        with patch("pypdf.PdfReader", side_effect=PdfReadError("bad pdf")):
            r = client.post(
                "/api/extract-materials",
                data={"task_type": "concept_review"},
                files={"file": ("broken.pdf", b"not a pdf", "application/pdf")},
            )
        assert r.status_code == 400
        assert "损坏" in r.json()["detail"]

    def test_image_only_pdf_reports_no_text(self, client):
        fake_page = MagicMock()
        fake_page.extract_text.return_value = ""
        fake_reader = MagicMock(is_encrypted=False, pages=[fake_page])

        with patch("pypdf.PdfReader", return_value=fake_reader):
            r = client.post(
                "/api/extract-materials",
                data={"task_type": "concept_review"},
                files={"file": ("scan.pdf", b"%PDF-fake-bytes", "application/pdf")},
            )
        assert r.status_code == 400
        assert "OCR" in r.json()["detail"]


class TestLegacyDocRejected:
    def test_doc_extension_rejected_with_clear_message(self, client):
        r = client.post(
            "/api/extract-materials",
            data={"task_type": "concept_review"},
            files={"file": ("old.doc", b"anything", "application/msword")},
        )
        assert r.status_code == 400
        assert ".docx" in r.json()["detail"]


class TestPlainTextUnaffected:
    def test_txt_still_works(self, client):
        r = client.post(
            "/api/extract-materials",
            data={"task_type": "concept_review"},
            files={"file": ("notes.txt", "游戏概念文档".encode("utf-8"), "text/plain")},
        )
        assert r.status_code == 200

    def test_unsupported_extension_rejected(self, client):
        r = client.post(
            "/api/extract-materials",
            data={"task_type": "concept_review"},
            files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
        )
        assert r.status_code == 400


class TestOversizeRejected:
    def test_oversize_file_rejected_while_reading(self, client):
        """超过上限的文件必须被拒（spec 3.6）：先整段 read() 再查大小会把
        超限请求体整个吸进内存，大小检查形同虚设——这里读满即中断。"""
        from app.api import MAX_UPLOAD_SIZE

        big = b"x" * (MAX_UPLOAD_SIZE + 1)
        r = client.post(
            "/api/extract-materials",
            data={"task_type": "concept_review"},
            files={"file": ("huge.txt", big, "text/plain")},
        )
        assert r.status_code == 413
        assert "超过限制" in r.json()["detail"]

    def test_just_under_limit_still_works(self, client):
        from app.api import MAX_UPLOAD_SIZE

        ok = ("内容" * 100).encode("utf-8")  # 远小于上限
        r = client.post(
            "/api/extract-materials",
            data={"task_type": "concept_review"},
            files={"file": ("notes.txt", ok, "text/plain")},
        )
        assert r.status_code == 200
