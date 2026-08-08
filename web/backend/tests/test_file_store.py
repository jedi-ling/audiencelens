"""上传图片落盘：刷新后对话里的图还得在。

此前图片**根本不落盘**：/api/uploads 把它 base64 成 data URI 直接返回，
一个字节都不写磁盘。图只活在浏览器内存里，刷新即消失——对话重放时那些图
永远回不来。

每条正向断言都配反向对照。只测"上传能读回来"的话，下面这些实现同样能全绿：
  · 不校验归属 —— 任何人凭 id 读走别人的截图
  · 归属校验回 403 —— 等于确认 id 存在，可用来枚举
  · 路径入库 —— 一旦某处能写这个字段就能读写磁盘任意位置
  · 落盘用用户传来的扩展名 —— 用户把任意内容叫成 .png
  · 删号只删库不删盘 —— 留下永远没人认领、连"这是谁的"都查不出的字节
"""

import io
import os

import pytest


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    yield


def _signup(client, email, password="password123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r.json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _upload(client, token, data=b"\x89PNG\r\n\x1a\n" + b"x" * 64, name="shot.png"):
    return client.post(
        "/api/uploads",
        files={"file": (name, io.BytesIO(data), "image/png")},
        headers=_h(token),
    )


class TestSurvivesReload:
    def test_upload_returns_retrievable_id(self, client):
        t = _signup(client, "file-a@example.com")
        r = _upload(client, t)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["file_id"], "没有返回 file_id，对话重放时无从引用这张图"
        assert body["url"] == f"/api/uploads/{body['file_id']}"
        # data URI 仍要返回：评审与追问链路一路把它当 image_url 传给模型
        assert body["image_data"].startswith("data:image/png;base64,")

        got = client.get(body["url"], headers=_h(t))
        assert got.status_code == 200
        assert got.headers["content-type"].startswith("image/png")

    def test_bytes_round_trip_exactly(self, client):
        """读回来的必须是原字节。截断/编码错误会让图看起来"在"但打不开。"""
        t = _signup(client, "file-rt@example.com")
        payload = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 8
        r = _upload(client, t, payload)
        got = client.get(r.json()["url"], headers=_h(t))
        assert got.content == payload

    def test_duplicate_upload_reuses_one_file(self, client):
        """同一张截图被反复拖进来是常态，不该在盘上存很多份。"""
        import hashlib

        t = _signup(client, "file-dup@example.com")
        # 用本用例独有的内容：测试库是跨用例共享的，用默认内容会数到别的用例的行
        payload = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + b"dup-case" * 8
        a = _upload(client, t, payload).json()
        b = _upload(client, t, payload).json()
        assert a["file_id"] == b["file_id"]

        from app.db import SessionLocal
        from app.models import UploadedFile

        digest = hashlib.sha256(payload).hexdigest()
        db = SessionLocal()
        try:
            n = db.query(UploadedFile).filter_by(sha256=digest).count()
            assert n == 1, "同一份内容落了多条记录"
        finally:
            db.close()

    def test_different_content_is_not_deduped(self, client):
        """反向对照：去重不能把不同的图也合并掉。"""
        t = _signup(client, "file-nodup@example.com")
        a = _upload(client, t, b"\x89PNG\r\n\x1a\n" + b"a" * 64).json()
        b = _upload(client, t, b"\x89PNG\r\n\x1a\n" + b"b" * 64).json()
        assert a["file_id"] != b["file_id"]


class TestOwnership:
    def test_other_user_cannot_read(self, client):
        a = _signup(client, "file-o-a@example.com")
        b = _signup(client, "file-o-b@example.com")
        url = _upload(client, a).json()["url"]

        r = client.get(url, headers=_h(b))
        # 反向对照：200 就是任何人凭 id 读走别人的截图
        assert r.status_code == 404
        # 必须 404 不是 403——403 等于确认该 id 存在
        assert r.status_code != 403
        # 确认本人仍然读得到，排除"其实谁都读不到"这种假通过
        assert client.get(url, headers=_h(a)).status_code == 200

    def test_dedup_does_not_cross_users(self, client):
        """两个人上传同一张图必须各存各的。按内容哈希全局去重会让
        B 的 file_id 指向 A 的文件，等于跨账号共享。"""
        a = _signup(client, "file-x-a@example.com")
        b = _signup(client, "file-x-b@example.com")
        same = b"\x89PNG\r\n\x1a\n" + b"same" * 16
        ida = _upload(client, a, same).json()["file_id"]
        idb = _upload(client, b, same).json()["file_id"]
        assert ida != idb


class TestStorageSafety:
    def test_path_is_derived_not_stored(self, client):
        """路径不入库。存任意路径字符串 = 一旦能写这个字段就能读写任意位置。"""
        from app.models import UploadedFile

        cols = {c.name for c in UploadedFile.__table__.columns}
        assert "path" not in cols and "storage_path" not in cols, (
            "模型里出现了路径列——路径必须由 id 推导"
        )

    def test_extension_comes_from_whitelist_not_user(self, client):
        """用户可以把任意内容叫成别的名字，落盘名必须由服务端决定。"""
        t = _signup(client, "file-ext@example.com")
        # 伪装成 .png 提交，但文件名带路径穿越
        r = client.post(
            "/api/uploads",
            files={"file": ("../../evil.png", io.BytesIO(b"\x89PNG\r\n\x1a\nzz"), "image/png")},
            headers=_h(t),
        )
        assert r.status_code == 200
        fid = r.json()["file_id"]

        from app.config import settings
        from app.db import SessionLocal
        from app.models import UploadedFile
        from app.services import file_store

        db = SessionLocal()
        try:
            row = db.get(UploadedFile, fid)
            path = os.path.abspath(file_store.storage_path(row.id, row.ext))
        finally:
            db.close()
        root = os.path.abspath(settings.upload_dir)
        assert path.startswith(root + os.sep), f"文件落到了上传目录之外：{path}"
        assert "evil" not in os.path.basename(path)

    def test_missing_file_on_disk_is_404_not_empty_200(self, client):
        """库里有记录、盘上没字节时不能回 200 空内容——那会让"图坏了"
        表现成"图是空的"，查不出原因。"""
        t = _signup(client, "file-gone@example.com")
        body = _upload(client, t).json()

        from app.db import SessionLocal
        from app.models import UploadedFile
        from app.services import file_store

        db = SessionLocal()
        try:
            row = db.get(UploadedFile, body["file_id"])
            os.remove(file_store.storage_path(row.id, row.ext))
        finally:
            db.close()

        assert client.get(body["url"], headers=_h(t)).status_code == 404


class TestDeletion:
    def test_deleting_account_removes_bytes_from_disk(self, client):
        t = _signup(client, "file-del@example.com")
        body = _upload(client, t).json()

        from app.db import SessionLocal
        from app.models import UploadedFile
        from app.services import file_store

        db = SessionLocal()
        try:
            row = db.get(UploadedFile, body["file_id"])
            path = file_store.storage_path(row.id, row.ext)
        finally:
            db.close()
        assert os.path.exists(path), "前置条件不成立：文件根本没落盘"

        from app.api.platform import DELETE_CONFIRM_PHRASE

        r = client.post(
            "/api/auth/me/delete",
            json={"password": "password123", "confirm": DELETE_CONFIRM_PHRASE},
            headers=_h(t),
        )
        assert r.status_code == 200, r.text
        stats = r.json()["detail"]
        assert stats["uploaded_files_deleted"] == 1
        assert stats["uploaded_bytes_freed"] > 0
        # 反向对照：只删库的实现会让这里仍然为 True
        assert not os.path.exists(path), "删号了但字节还在盘上"
