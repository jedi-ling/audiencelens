"""后台管理面板的具名账号登录。

会话令牌用 AL_ADMIN_TOKEN 本身作签名密钥（不是 AL_JWT_SECRET）：这样一来
- 不需要新增一个配置项；
- 与产品侧用户会话（signed by jwt_secret）是完全独立的信任根，两者的令牌
  互相不能串用；
- 轮换/清空 AL_ADMIN_TOKEN 会让所有已登录的具名账号会话跟着一起失效——
  这是期望行为：换主密钥就是要求所有人重新登录，而不是留一批"旧信任根
  签发、新主密钥治下继续有效"的令牌。
subject 固定加 "admin:" 前缀，deps.require_admin 靠这个前缀区分「这是一个
账号会话令牌」还是别的什么东西误传进来的字符串。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import AdminUser

_SUBJECT_PREFIX = "admin:"
SESSION_TTL_SECONDS = 12 * 3600  # 后台会话比产品侧用户会话短——管理员操作敏感，不图免登录持久
MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 8


def create_admin_user(db: Session, username: str, password: str) -> AdminUser:
    username = username.strip()
    if len(username) < MIN_USERNAME_LENGTH:
        raise ValueError(f"用户名至少 {MIN_USERNAME_LENGTH} 个字符")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"密码至少 {MIN_PASSWORD_LENGTH} 个字符")
    if db.query(AdminUser).filter(AdminUser.username == username).first() is not None:
        raise ValueError("用户名已存在")
    user = AdminUser(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> Optional[AdminUser]:
    user = db.query(AdminUser).filter(AdminUser.username == username.strip()).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def issue_session_token(user: AdminUser, admin_secret: str) -> str:
    return create_token(f"{_SUBJECT_PREFIX}{user.id}", admin_secret, SESSION_TTL_SECONDS)


def resolve_session(db: Session, token: str, admin_secret: str) -> Optional[AdminUser]:
    """把请求头里的令牌解成具名账号；不是这类令牌或已失效则返回 None。

    调用方（deps.require_admin）会先比对完 legacy 静态令牌落空之后才走到这里，
    所以这里不需要再判断 token 是否等于静态令牌本身。
    """
    try:
        payload = decode_token(token, admin_secret)
    except ValueError:
        return None
    subject = payload.get("sub", "")
    if not subject.startswith(_SUBJECT_PREFIX):
        return None
    user_id = subject[len(_SUBJECT_PREFIX):]
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if user is None or not user.is_active:
        return None
    return user


def touch_last_login(db: Session, user: AdminUser) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()


def deactivate(db: Session, user_id: str) -> bool:
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if user is None:
        return False
    user.is_active = False
    db.commit()
    return True


def list_admin_users(db: Session) -> list:
    return db.query(AdminUser).order_by(AdminUser.created_at.asc()).all()
