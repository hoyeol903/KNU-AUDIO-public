import hashlib
import pytest
from community.admin_credentials import password_hash


def test_password_hash():
    password = '관리자용 긴 비밀번호 1234'
    one, two = password_hash(password), password_hash(password)
    assert one != two
    scheme, rounds, salt, digest = one.split(':')
    assert scheme == 'pbkdf2-sha256'
    assert rounds == '100000'  # Workers PBKDF2 상한
    assert hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds)).hex() == digest
    for invalid in ['short', 'a' * 257]:
        with pytest.raises(ValueError):
            password_hash(invalid)
