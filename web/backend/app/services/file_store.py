"""上传文件的落盘存储。库里只存元信息，字节在磁盘上。

这一层复活了 AL_UPLOAD_DIR —— 它此前是**死配置**：config.py 里定义了，
全仓没有任何一行代码读它。同时 data/uploads/ 下躺着 141 个孤儿文件
（205 KB，2025 年 7 月的旧代码遗留），零数据库引用、零读取入口。
清理脚本见 scripts/cleanup_orphan_uploads.py。

三条安全约束，每条都对应一个具体的失败方式：
  · 路径由 id 推导，绝不入库 —— 存任意路径字符串意味着一旦某处能写这个字段，
    就能读写磁盘上任意位置
  · 按 id 前两位分片 —— 单目录堆到十万个文件时，很多文件系统的 ls/遍历
    会退化到不可用
  · 扩展名只从白名单映射取，不取用户传来的那个 —— 用户可以叫它 .png
    但内容是别的，落盘名必须由服务端决定
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models import UploadedFile

ANON = "anonymous"


def _owner(user_id: Optional[str]) -> str:
    return user_id or ANON


def _root() -> str:
    return settings.upload_dir


def storage_path(file_id: str, ext: str) -> str:
    """由 id 推导磁盘路径。id 是 uuid4，不含分隔符，拼不出 ../。"""
    safe_id = os.path.basename(file_id)  # 双保险：即便上游传进奇怪的东西也压平
    return os.path.join(_root(), safe_id[:2], f"{safe_id}{ext}")


def save_bytes(
    db: Session,
    user_id: Optional[str],
    raw: bytes,
    media_type: str,
    ext: str,
    filename: Optional[str] = None,
) -> UploadedFile:
    """写盘并登记。同一用户重复上传同一张图只落一份。"""
    owner = _owner(user_id)
    digest = hashlib.sha256(raw).hexdigest()

    existing = (
        db.query(UploadedFile)
        .filter(UploadedFile.user_id == owner, UploadedFile.sha256 == digest)
        .first()
    )
    if existing is not None and os.path.exists(storage_path(existing.id, existing.ext)):
        # 必须同时检查磁盘：只查库会在文件被外部删掉后返回一条指向空气的记录，
        # 之后每次读都 404，而用户看到的是"上传成功了"。
        return existing

    row = UploadedFile(
        user_id=owner,
        filename=filename,
        media_type=media_type,
        ext=ext,
        byte_size=len(raw),
        sha256=digest,
    )
    db.add(row)
    db.flush()  # 要先拿到 id 才能算路径

    path = storage_path(row.id, ext)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 先写临时文件再原子改名：直接写目标路径时，进程在写一半时挂掉会留下
    # 一个大小对不上的半截文件，而库里那条记录看起来完全正常。
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(raw)
    os.replace(tmp, path)

    db.commit()
    db.refresh(row)
    return row


def get_owned(db: Session, file_id: str, user_id: Optional[str]) -> Optional[UploadedFile]:
    """取一份属于该用户的文件。不属于则 None（调用方回 404，不回 403——
    403 等于确认该 id 存在，可用来枚举）。"""
    row = db.get(UploadedFile, file_id)
    if row is None:
        return None
    if _owner(row.user_id) != _owner(user_id):
        return None
    return row


def read_bytes(row: UploadedFile) -> Optional[bytes]:
    path = storage_path(row.id, row.ext)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def delete_for_user(db: Session, user_id: str) -> Tuple[int, int]:
    """删掉某用户的全部文件（磁盘 + 库）。返回 (删除行数, 释放字节数)。

    先删盘再删库：反过来的话，删库成功而删盘失败会留下永远没人认领的字节，
    因为已经没有任何记录指向它们了。
    """
    rows = db.query(UploadedFile).filter(UploadedFile.user_id == user_id).all()
    freed = 0
    for r in rows:
        path = storage_path(r.id, r.ext)
        try:
            if os.path.exists(path):
                freed += os.path.getsize(path)
                os.remove(path)
        except OSError:
            # 删不掉某个文件不该让整个删号请求失败——用户的账号必须能删掉。
            # 残留的字节由 scripts/cleanup_orphan_uploads.py 兜底。
            pass
        db.delete(r)
    return len(rows), freed


def usage_bytes(db: Session, user_id: Optional[str]) -> int:
    """该用户占用的磁盘字节数。有了它，"图片占多少空间"才是可查的数字
    而不是猜测。"""
    from sqlalchemy import func

    return (
        db.query(func.coalesce(func.sum(UploadedFile.byte_size), 0))
        .filter(UploadedFile.user_id == _owner(user_id))
        .scalar()
        or 0
    )
