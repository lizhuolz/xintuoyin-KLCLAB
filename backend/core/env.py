import os


def load_env_from_file(env_file: str) -> None:
    if not os.path.exists(env_file):
        return

    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("export "):
                continue

            content = line[7:].strip()
            if "=" not in content:
                continue

            key, value = content.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if " # " in value:
                value = value.split(" # ")[0].strip()
            os.environ[key.strip()] = value
