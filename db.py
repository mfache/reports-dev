import pymysql

DB_ENV_FILE = "/etc/boitier-fleet/db.env"

def _read_env(path):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env

_ENV = _read_env(DB_ENV_FILE)

def get_db():
    return pymysql.connect(
        host=_ENV.get("DB_HOST", "localhost"),
        user=_ENV.get("DB_USER", "boitier_app"),
        password=_ENV.get("DB_PASSWORD", ""),
        database=_ENV.get("DB_NAME", "dt"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
