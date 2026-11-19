# Release Notes Nginx Sync


## v1.1.1 - project is now deprecated

This is the final release of `nginx-sync`.

This project is no longer developed; it has been rewritten in Rust as
**nginxy** (https://github.com/Transparent-Systems/nginxy), which performs the
same synchronisation as a single native binary with no Python runtime and no
PyInstaller bundle. The README documents how to migrate, including the renamed
credential keys in `.env`.

The Linux and Windows binaries below remain available and keep working for
existing deployments, but no further features or fixes will be added.

## v1.1.0 - add Linux binary

Added build-linux.yml to the GitHub workflows.
Whenever a new release is published, that will trigger a GitHub Action to build a new Linux binary.
Binary executed successfully on Debian 11 (glibc 2.31), Ubuntu 22.04 (2.35) and Ubuntu 24.04 (2.39); ELF x86-64, no Python needed.
--version prints the version from log.yaml (works on a binary with no configuration), 
and --config-dir <PATH> keeps config.yaml, log.yaml and .env — plus the logs — in one folder of your choosing. 
Ctrl-C now always shuts down cleanly.

Added build-windows.yml: every release also publishes a single-file nginx-sync.exe (Windows 10/11 x64, no installation). Config files are read as UTF-8, including the BOM that Windows editors add.

## v1.0.0 - first release

Initial release of Nginx Sync.  
This release has been tested on Linux (Ubuntu 22.04)
