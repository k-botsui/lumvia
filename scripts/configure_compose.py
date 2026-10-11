"""Generate private container settings without changing an existing installation."""

import secrets

from private_paths import STATE_ROOT


def configure():
    target = STATE_ROOT / "compose.env"
    if target.exists():
        return target
    STATE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)
    values = {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "RABBITMQ_PASSWORD": secrets.token_urlsafe(32),
        "SECRET_KEY": secrets.token_urlsafe(48),
        "ADMIN_EMAIL": "owner@lumvia.local",
        "ADMIN_PASSWORD": password,
    }
    with target.open("x", encoding="utf-8", newline="\n") as output:
        target.chmod(0o600)
        output.write("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    login = STATE_ROOT / "Dockerログイン情報.txt"
    with login.open("w", encoding="utf-8", newline="\n") as output:
        login.chmod(0o600)
        output.write(f"Docker版の初期アカウント\nowner@lumvia.local\n{password}\n")
    return target


if __name__ == "__main__":
    print(f"Settings: {configure()}. Credentials were not printed or changed.")
