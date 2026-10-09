"""관리자 비밀번호를 화면·파일에 남기지 않고 Worker Secrets에 등록한다."""
import argparse
import getpass
import hashlib
from pathlib import Path
import secrets
import subprocess


def password_hash(password):
    if not 12 <= len(password) <= 256:
        raise ValueError('비밀번호는 12~256자로 정해 주세요.')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210000)
    return f'pbkdf2-sha256:210000:{salt.hex()}:{digest.hex()}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    if not args.config.is_file():
        parser.error('실제 Worker 설정 파일을 지정해 주세요.')
    username = input('관리자 아이디: ').strip()
    if not username or len(username) > 80:
        parser.error('아이디는 1~80자로 정해 주세요.')
    password = getpass.getpass('관리자 비밀번호 (12자 이상): ')
    if password != getpass.getpass('비밀번호 다시 입력: '):
        parser.error('비밀번호가 일치하지 않아요.')
    try:
        stored = password_hash(password)
        for key, value in [('ADMIN_USERNAME', username), ('ADMIN_PASSWORD_HASH', stored)]:
            subprocess.run(['npx', 'wrangler@4', 'secret', 'put', key, '--config', str(args.config)], input=value+'\n', text=True, check=True)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'계정 등록 실패: {error}\n')
    print('관리자 계정을 등록했어요. 기존 로그인은 만료됩니다.')


if __name__ == '__main__':
    main()
