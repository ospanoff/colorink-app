# Deploying Colorink

This folder contains a **systemd** unit template to run the app on a Linux host with [systemd](https://systemd.io/). The process listens on **port 8000** and is reachable on the **LAN** by default (bind `0.0.0.0`).

## Layout

- Install the repository as **`~/colorink-app`** for whatever Unix account should own the process (for example the user you use over SSH).
- The template **`systemd/colorink@.service`** enables **`colorink@YOUR_LOGIN`**. It uses **`/home/YOUR_LOGIN/colorink-app`**, which matches **`~/colorink-app`** when home is the usual **`/home/<login>`**. If your home directory is elsewhere (LDAP, etc.), edit **`WorkingDirectory=`** and **`ExecStart=`** in a **drop-in** or a copied unit.
- **`User=`** / **`Group=`** come from the instance name (the segment after `@`).

## Prerequisites on the server

- **systemd** (common on most Linux images).
- **[uv](https://docs.astral.sh/uv/)** on `PATH` when you run install commands (install as the same user that will own the app).
- **Git** is optional on the server if you deploy only with **rsync** from another machine.

The app needs **Python 3.13** (see [`requires-python`](../pyproject.toml) and the root [`README.md`](../README.md)). **`uv sync`** creates the venv, **installs a matching interpreter via uv if the host does not have one**, and installs dependencies. From `~/colorink-app`:

```bash
cd ~/colorink-app
uv sync
```

If you prefer to install the interpreter explicitly first: `uv python install 3.13`, then `uv sync`.

## Install and enable

### With rsync (from your computer)

From your **local repository root** (the directory that contains `pyproject.toml`). Replace `YOUR_UNIX_USER`, `YOUR_SERVER`, and adjust the remote path if it is not `~/colorink-app`.

```bash
rsync -avz --delete \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' \
  --exclude '.ty_cache/' \
  --exclude 'data/' \
  --exclude '*.db' \
  --exclude '.env' \
  --exclude 'dist/' \
  --exclude '*.egg-info/' \
  --exclude '.git/' \
  ./ YOUR_UNIX_USER@YOUR_SERVER:~/colorink-app/
```

Omit `--exclude '.git/'` if you want a `.git` directory on the server (for example to run `git` there later).

**On the server** (SSH as `YOUR_UNIX_USER`):

```bash
cd ~/colorink-app
uv sync
```

### With Git (on the server)

As the owning user:

```bash
git clone <YOUR_REPO_URL> ~/colorink-app
cd ~/colorink-app
uv sync
```

### systemd

Run these **from a normal SSH session as the user that owns `~/colorink-app`** (not from `sudo su -`, where `$USER` would be `root`). Your shell expands **`$USER`** before `sudo` runs.

```bash
sudo cp ~/colorink-app/deploy/systemd/colorink@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now "colorink@${USER}.service"
```

Check:

```bash
systemctl status "colorink@${USER}.service"
curl -sS http://127.0.0.1:8000/health
```

If you must enable the unit **for another user** while logged in as root, name them explicitly: `sudo systemctl enable --now colorink@someuser.service`.

From another machine on the same network (if the host firewall allows it): `http://<server-ip>:8000/docs`.

## Logs and lifecycle

```bash
sudo journalctl -u "colorink@${USER}.service" --since today --no-pager
sudo journalctl -u "colorink@${USER}.service" -f
```

After changing code or dependencies:

**If you use rsync**, run the same `rsync` command again from your machine, then on the server:

```bash
cd ~/colorink-app && uv sync
sudo systemctl restart "colorink@${USER}.service"
```

**If you use Git on the server**:

```bash
cd ~/colorink-app && git pull && uv sync
sudo systemctl restart "colorink@${USER}.service"
```

## Firewall and hardening

The unit binds **`0.0.0.0:8000`**, so anything allowed to reach that port on the host can call the API. Open **TCP 8000** in the host firewall only if you want LAN (or wider) access. For a stricter setup, change **`--host 0.0.0.0`** to **`127.0.0.1`** in the unit (or a **drop-in override**) and put a reverse proxy with TLS in front.

## Configuration

Optional environment variables can be added under `[Service]` in the unit file or via **`sudo systemctl edit "colorink@${USER}.service"`** (again, run from the owning user’s shell so `$USER` is correct). See the root README for **`COLORINK_DATABASE_PATH`** and defaults (`data/colorink.db` under the app directory).
