# PANDA

PANDA (Python Automation for Network Device Access) is a web interface for network automation workflows using Flask + Nornir.

This project lets you:
- Select devices from local inventory files or NetBox.
- Run Get Configs tasks from the web UI.
- Manage inventory folder and NetBox settings in a settings modal.

## Tech Stack
- Python 3
- Flask
- Nornir
- Netmiko
- YAML-based configuration (`config.yaml`)

## Requirements
1. Install Python 3.10+.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   ```

   Windows (PowerShell):
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   Linux/macOS (bash/zsh):
   ```bash
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Environment Configuration
Copy `.env.example` to `.env` and adjust values:

```env
PORT=5001
ROOT_DIRECTORY=.
INVENTORY_DIRECTORY=inputfiles/inventory
NETBOX_URL=
NETBOX_TOKEN=
```

Notes:
- `ROOT_DIRECTORY` is the main workspace folder for a client context.
  PANDA uses it as the base folder to read and write project data (for example `inputfiles/` and `outputfiles/`).
- `INVENTORY_DIRECTORY` must contain `hosts.yaml`, `groups.yaml`, and `defaults.yaml`.
- `NETBOX_URL` and `NETBOX_TOKEN` are optional unless you want NetBox source mode.

## Run the App
```bash
python main.py
```

Open `http://127.0.0.1:5001` (or your configured `PORT`).

## Configuration Source
`config.yaml` controls user-defined device data shown in the UI:
- `user_defined.device_data`

This is where you define the commands/data PANDA should run and collect from devices.
The app builds the Get Configs options from this section.
