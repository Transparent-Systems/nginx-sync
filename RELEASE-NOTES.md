# Release Notes Nginx Sync


## v1.1.0 - add Linux binary

Added build-linux.yml to the GitHub workflows.
Whenever a new release is published, that will trigger a GitHub Action to build a new Linux binary.
Binary executed successfully on Debian 11 (glibc 2.31), Ubuntu 22.04 (2.35) and Ubuntu 24.04 (2.39); ELF x86-64, no Python needed.
--version prints the version from log.yaml (works on a binary with no configuration), 
and --config-dir <PATH> keeps config.yaml, log.yaml and .env — plus the logs — in one folder of your choosing. 
Ctrl-C now always shuts down cleanly.

## v1.0.0 - first release

Initial release of Nginx Sync.  
This release has been tested on Linux (Ubuntu 22.04)
