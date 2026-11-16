# Nginx Sync

![AIP logo](https://aip.transparent.co.nz/wp-content/uploads/2025/06/AIP_grey_transparent_background_github-e1750625832556.png)

## 🚀 Quick Start

1. **Running nginx-sync**:

    *Running from Source*
    
    a. **Install Python**: Download from [python.org](https://www.python.org/downloads/).
       Python 3.10 or newer is required (the release binary is built with 3.12).

    b. **Download nginx-sync from Github**

      ```bash
      For example type command:  
      git clone https://github.com/Transparent-Systems/nginx-sync.git 
      ```
          
    c. **Create file .env and add two lines**
    ```bash
      Example content of .env:
      NPM_IDENTITY=your_identity
      NPM_SECRET=your_secret
    ```
  
    d. **Setup Python Virtual Environment on Linux**
    ```bash
      cd nginx-sync
      python3.12 -m venv .venv        # any Python 3.10 or newer
      source .venv/bin/activate
      pip install -r requirements.txt
      Create file .env and add two lines. For example:

      Run main.py:
      python3 main.py
    ```
    e. **Setup Python Virtual Environment on Windows**
    ```bash
      cd nginx-sync
      python -m venv .venv
      ./.venv/Scripts/activate
      pip install -r requirements.txt
      Run main.py:
      python main.py
    ```

## 📦 Prebuilt Binaries

Every release tag builds self-contained binaries — no Python needed on either
machine, see `.github/workflows/build-linux.yml` and
`.github/workflows/build-windows.yml`. They are the same program, so you can run
the Windows one on the workstation you manage the servers from and the Linux one
on the servers themselves.

### Linux

1. Download `nginx-sync` and `nginx-sync.sha256` from the
   [Releases](https://github.com/Transparent-Systems/nginx-sync/releases) page.

2. Verify the download and make it executable (the executable bit is not kept
   by the download):

    ```bash
    sha256sum -c nginx-sync.sha256
    chmod +x nginx-sync
    ```

3. Put `config.yaml`, `log.yaml` and `.env` next to the binary — they are read
   from the binary's own folder, not from the current directory — and start it:

    ```bash
    ./nginx-sync -p 30
    ```

    To keep the configuration somewhere else (with the binary in
    `/usr/local/bin`, for example), name that folder instead:

    ```bash
    ./nginx-sync --config-dir /etc/nginx-sync -p 30
    ```

    `./nginx-sync -h` lists all arguments and `./nginx-sync --version` prints the
    version from `log.yaml`. Logs are written to the `logs` folder inside the
    configuration folder.

The Linux binary is built in a Debian bullseye container (glibc 2.31), so it runs
on Ubuntu 22.04 and newer, Debian 11 and newer, and RHEL 9 and newer, on x86_64.

### Windows

1. Download `nginx-sync.exe` and `nginx-sync.exe.sha256` from the
   [Releases](https://github.com/Transparent-Systems/nginx-sync/releases) page.

2. Verify the download — the `.sha256` file holds the hash followed by the file
   name, exactly as `Get-FileHash` prints it:

    ```powershell
    Get-FileHash .\nginx-sync.exe -Algorithm SHA256
    ```

3. Put `config.yaml`, `log.yaml` and `.env` in a folder and start the sync from
   a terminal, so the log lines are visible:

    ```powershell
    .\nginx-sync.exe --config-dir C:\ProgramData\nginx-sync -p 30
    ```

    Or keep the configuration next to the exe and just run `.\nginx-sync.exe`.
    `-h` and `--version` work here too, and the logs go to
    `logs\nginx_sync.log` inside the configuration folder.

    Windows SmartScreen may warn that the program is unrecognised because the exe
    is not code-signed: choose **More info → Run anyway**. To run it unattended,
    start it from Task Scheduler (or with a service wrapper such as NSSM) instead
    of a console window.

The Windows binary is a single file that carries Python and the C runtime, so it
needs no installation and runs on Windows 10 and 11 (x64).

### Building it yourself

Run `.venv/bin/python build_project.py` (or `.venv\Scripts\python build_project.py`
on Windows); `build_project.py -h` shows the options. Name the virtualenv
interpreter explicitly: after activating the virtualenv, a `python` that comes
from pyenv or the system may still be older than the 3.10 that
`requirements.txt` needs.

## Script Arguments
You can call `nginx-sync` with several arguments.
Command line arguments will override properties in config.yaml.
To see all arguments type:
python3 main.py -h
OR on Windows:
python main.py -h

| Argument | Description |
| -------- | ----------- |
| `-p`, `--period <SECONDS>` | Seconds between syncs (default 30; `0` syncs once and exits) |
| `-l`, `--log-level <LEVEL>` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` or `NONE` |
| `--dry-run` | Report what would change; the target servers are left untouched |
| `--config-dir <PATH>` | Folder holding `config.yaml`, `log.yaml` and `.env` (default: the folder of the binary, or of `main.py` when run from source) |
| `--version` | Print the version recorded in `log.yaml` and exit |


* Nginx credentials stored in .env file
* Source and target Nginx server details stored in config.yaml file
* Log configuration stored in log.yaml file
* Nginx Sync can handle one or more target servers
 


## Features

* Nginx credentials stored in .env file
* Source and target Nginx server details stored in config.yaml file
* Log configuration stored in log.yaml file
* Nginx Sync can handle one or more target servers
 

## License

This is free software under the terms of the MIT license included in this package.  
See file: LICENSE


## Why Nginx Sync?
The use case for Nginx Sync is:
- You run servers behind a cloudflare tunnel using a cloudflared daemon
- The Cloudflare tunnel connects to a Nginx server that forwards request to web servers, cloud server etc.
- You have 2 or more servers configured with a combo of {cloudflared and Nginx server}
  This provides High Availability (HA) and Load Balancing; if one server goes down, traffic continues to flow through the others.
- Now, when make changes to the main Nginx server, you want to propagate those changes to the other Nginx servers on your network

Nginx Sync retrieves the proxy hosts of the source Nginx server, checks if there have been any changes and propagates those changes to all target Nginx servers.


## Acknowledgments

This project was developed with the Google Gemini Code Assist extension in VS Code.

### 👤 Author

John Zoetebier

* Website: [aip.transparent.co.nz](http://aip.transparent.co.nz)
