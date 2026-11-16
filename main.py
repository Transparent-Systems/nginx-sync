import argparse
import time
import requests
import json
import yaml
import os
import signal
import sys
import dotenv
import logging
from typing import List, Dict, Any, Optional, Set, Union
from logging.handlers import RotatingFileHandler


"""
This script synchronizes proxy host configurations from a source NPM instance to one or more target NPM instances.
It performs the following steps:
1. Loads configuration from config.yaml and environment variables from .env.
2. Authenticates with the source NPM instance to get a token.
3. For each target NPM instance:
   a. Authenticates to get a token.
   b. Fetches proxy host configurations from the source.
   c. Fetches existing proxy host configurations from the target.
   d. Compares the two sets of configurations:
      - If a host exists in the source but not in the target, it creates it on the target.
      - If a host exists in both but has different configurations, it updates the target host to match the source.
      - If a host exists in the target but not in the source, it deletes it from the target.
4. Logs all actions and any errors encountered during the process.

Example content of .env:
NPM_IDENTITY=your_identity
NPM_SECRET=your_secret
"""

def get_script_dir() -> str:
    """
    Returns the folder holding config.yaml, log.yaml and .env.

    A PyInstaller build unpacks main.py into a temporary folder, so __file__
    points there instead of the folder the binary was started from. The folder
    of the executable is the one the user put the configuration files in, so
    that is what a frozen binary has to use.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

SCRIPT_DIR = get_script_dir()
dotenv.load_dotenv(os.path.join(SCRIPT_DIR, '.env'))

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    if config_path is None:
        config_path = os.path.join(SETTINGS_DIR, "config.yaml")
    try:
        # utf-8-sig accepts both plain UTF-8 and the BOM that Windows editors
        # such as Notepad write; the default locale encoding would fail on both.
        with open(config_path, 'r', encoding='utf-8-sig') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        # The binary ships without configuration, so this is the first thing a
        # new user hits. Explain what is missing instead of showing a traceback.
        print(f"ERROR: configuration file not found: {config_path}", file=sys.stderr)
        print(f"Copy config.yaml, log.yaml and .env into {os.path.dirname(config_path)},", file=sys.stderr)
        print("or name another folder with --config-dir <PATH>.", file=sys.stderr)
        sys.exit(2)

def setup_logging(log_config_path: Optional[str] = None) -> logging.Logger:
    """
    Sets up a revolving file logger and a console logger based on the provided YAML configuration.
    """
    if log_config_path is None:
        log_config_path = os.path.join(SETTINGS_DIR, "log.yaml")
        
    try:
        with open(log_config_path, 'r', encoding='utf-8-sig') as file:
            log_cfg = yaml.safe_load(file).get('logging', {})
    except (FileNotFoundError, yaml.YAMLError):
        log_cfg = {}

    log_folder = log_cfg.get('folder', 'logs')
    if not os.path.isabs(log_folder):
        log_folder = os.path.join(SETTINGS_DIR, log_folder)

    if not os.path.exists(log_folder):
        os.makedirs(log_folder)

    log_file = os.path.join(log_folder, log_cfg.get('file_name', 'nginx_sync.log'))
    log_level_str = log_cfg.get('log_level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger("nginx_sync")
    logger.setLevel(log_level)

    # Prevents duplicate log entries if script is imported or re-initialized
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # File Handler (Revolving)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=log_cfg.get('max_bytes', 10485760),
            backupCount=log_cfg.get('max_backup_count', 3),
            # Write UTF-8 everywhere: the Windows default code page cannot
            # encode every hostname a log line may quote.
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

# Version metadata. log.yaml already records the version; build_project.py and
# utils/release_notes.py read the same field, so --version and a release cannot
# disagree about it.
VERSION_FILE = "log.yaml"
FALLBACK_VERSION = "unknown"

# Populated by load_settings() once the command line has been parsed: the folder
# that holds config.yaml is itself a command line option, so nothing can be read
# at import time.
SETTINGS_DIR: str = SCRIPT_DIR
CONFIG: Dict[str, Any] = {}
SOURCE_CONFIG: Dict[str, Any] = {}
TARGETS: List[Dict[str, Any]] = []
logger: logging.Logger = logging.getLogger("nginx_sync")


def read_version(directory: Optional[str] = None) -> str:
    """
    Returns the version recorded in log.yaml, or "unknown" when it cannot be read.

    The folder holding the configuration wins. A binary shipped without one falls
    back to the log.yaml bundled into it at build time (see build_project.py), so
    a freshly downloaded nginx-sync can still report its version.
    """
    candidates: List[str] = [directory or SETTINGS_DIR]
    bundled = getattr(sys, '_MEIPASS', None)
    if bundled and bundled not in candidates:
        candidates.append(bundled)

    for base in candidates:
        path = os.path.join(base, VERSION_FILE)
        try:
            with open(path, 'r', encoding='utf-8-sig') as file:
                version = (yaml.safe_load(file) or {}).get('version')
        except (OSError, yaml.YAMLError):
            continue
        if version:
            return str(version)

    return FALLBACK_VERSION


def load_settings(config_dir: Optional[str] = None) -> None:
    """
    Loads .env, config.yaml and log.yaml from the folder that holds them.

    .env is read first so credentials are available for the endpoints that take
    them from the environment, and the relative log folder in log.yaml is
    resolved against that same directory rather than against the binary.
    """
    global SETTINGS_DIR, CONFIG, SOURCE_CONFIG, TARGETS, logger

    SETTINGS_DIR = os.path.abspath(config_dir) if config_dir else SCRIPT_DIR
    dotenv.load_dotenv(os.path.join(SETTINGS_DIR, '.env'))
    CONFIG = load_config(os.path.join(SETTINGS_DIR, "config.yaml"))
    SOURCE_CONFIG = CONFIG.get('source', {})
    TARGETS = CONFIG.get('targets', [])
    logger = setup_logging(os.path.join(SETTINGS_DIR, "log.yaml"))

# Fields returned by NPM API that should not be sent back in creation/update payloads
EXCLUDED_KEYS: Set[str] = {'id', 'owner_user_id', 'created_on', 'modified_on', 'user'}
# Default timeout for API requests in seconds
DEFAULT_TIMEOUT: int = 10

def get_auth_payload(config_node: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to get auth payload from config node or environment variables."""
    return config_node.get('auth_payload') or {
        "identity": os.getenv("NPM_IDENTITY"),
        "secret": os.getenv("NPM_SECRET")
    }

def missing_credentials() -> List[str]:
    """
    Returns the source or targets that have no identity/secret to log in with.

    NPM answers a token request without credentials with "400 Bad Request", so
    without this check a missing .env shows up as a wall of failed logins every
    sync cycle instead of one error that names the cause.
    """
    endpoints: List[Any] = [("source", SOURCE_CONFIG)]
    endpoints.extend((target.get('name', target['url']), target) for target in TARGETS)

    missing: List[str] = []
    for name, node in endpoints:
        payload = get_auth_payload(node)
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        if not payload.get('identity') or not payload.get('secret'):
            missing.append(name)
    return missing

def main(period: int = 60, dry_run: bool = False) -> None:
    mode_str = " (DRY RUN MODE)" if dry_run else ""
    logger.info(f"Starting Sync{mode_str}: {len(TARGETS)} targets configured.")
    
    # Consolidate all sessions (source and targets) into a single dictionary
    sessions: Dict[str, requests.Session] = {SOURCE_CONFIG['url']: requests.Session()}
    for target in TARGETS:
        sessions[target['url']] = requests.Session()

    # Track targets that need a sync (either due to source changes or previous failures)
    unsynced_targets: Set[str] = {target['url'] for target in TARGETS}
    last_auth_time = 0
    AUTH_REFRESH_INTERVAL = 12 * 3600  # Refresh tokens every 12 hours (NPM default is 24h)

    previous_source_hosts: Optional[List[Dict[str, Any]]] = None
    source_url = SOURCE_CONFIG['url']

    try:
        while True:
            # Phase 0: Periodic token invalidation to force refresh
            if time.time() - last_auth_time > AUTH_REFRESH_INTERVAL:
                logger.info("Token refresh interval reached. Invalidating sessions.")
                for s in sessions.values():
                    s.headers.pop("Authorization", None)
                last_auth_time = time.time()

            # Lazy-authenticate Source Session
            session_s = sessions[source_url]
            if "Authorization" not in session_s.headers:
                token = get_token(source_url, get_auth_payload(SOURCE_CONFIG))
                if token:
                    session_s.headers.update({"Authorization": f"Bearer {token}"})

            if "Authorization" not in session_s.headers:
                logger.error("Source session not authenticated. Skipping cycle.")
                if period <= 0: break
                time.sleep(period)
                continue

            # Phase 1: Fetch source hosts
            endpoint = f"{source_url}/nginx/proxy-hosts"
            logger.info(f"Fetching proxy hosts from {endpoint}")
            try:
                source_resp = session_s.get(endpoint, timeout=DEFAULT_TIMEOUT)
                if source_resp.status_code == 200:
                    source_hosts = source_resp.json()
                else:
                    logger.error(f"Failed to fetch proxy hosts from source: {source_resp.status_code}")
                    source_hosts = None
            except requests.exceptions.RequestException as e:
                logger.error(f"Connection error to source: {e}")
                session_s.headers.pop("Authorization", None)
                source_hosts = None

            if source_hosts is None:
                if period <= 0: break
                time.sleep(period)
                continue

            # Phase 2: Detect Source Changes
            source_changed = (source_hosts != previous_source_hosts)
            if source_changed:
                # If source changed, mark all targets as needing a sync
                unsynced_targets.update([t['url'] for t in TARGETS])
                
                if previous_source_hosts is None:
                    logger.info(f"Initial sync: Source has {len(source_hosts)} proxy hosts.")
                else:
                    logger.info(f"Source change detected ({len(source_hosts)} hosts).")

                # Only "consume" the change if we aren't in dry run mode
                if not dry_run:
                    previous_source_hosts = source_hosts

            # Phase 3: Sync Target Loop
            if period > 0 and not source_changed and not unsynced_targets:
                logger.info("No changes in source and all targets are in sync.")
                logger.info(f"Next sync in {period} seconds.")
                time.sleep(period)
                continue

            if period <= 0:
                logger.info("One-time sync mode. Proceeding with sync to targets.")
            elif unsynced_targets and not source_changed:
                logger.info(f"Retrying sync for {len(unsynced_targets)} unsynced target(s).")

            for target in TARGETS:
                t_url = target['url']
                if t_url not in unsynced_targets:
                    continue

                logger.info(f"--- Syncing to Target: {target['name']} ({t_url}) ---")
                session_t = sessions[t_url]
                
                # Lazy-authenticate Target Session
                if "Authorization" not in session_t.headers:
                    token = get_token(t_url, get_auth_payload(target))
                    if token:
                        session_t.headers.update({"Authorization": f"Bearer {token}"})

                if "Authorization" in session_t.headers:
                    success = sync_to_target(source_hosts, session_t, t_url, dry_run)
                    # Only remove from unsynced list if sync succeeded and not in dry run
                    if success and not dry_run:
                        unsynced_targets.discard(t_url)
                else:
                    logger.warning(f"Skipping target {target['name']} - Authentication failed.")
            
            if period <= 0:
                logger.info("One-time sync completed. Exiting.")
                break
            else:
                logger.info(f"Sync completed. Next sync in {period} seconds.")
            time.sleep(period)
    except KeyboardInterrupt:
        # The shutdown itself lives in cli(): logging from inside this handler
        # is what used to leave a traceback, because a second Ctrl-C (the
        # bootloader forwards the first) interrupted the log call.
        raise

def describe_http_failure(response: requests.Response) -> str:
    """
    Returns the reason NPM gave for rejecting a request.

    raise_for_status() only reports "400 Client Error", which hides the bit that
    matters: NPM answers 400 when identity or secret is missing from the payload
    and names the offending field in the response body.
    """
    detail = " ".join(response.text.split())[:300]
    return f"HTTP {response.status_code}" + (f": {detail}" if detail else "")

def get_token(url: str, auth_payload: Union[Dict[str, Any], str, None] = None) -> Optional[str]:
    """
    Obtains an authentication token from the NPM instance at the given URL using the provided payload.
    """
    if isinstance(auth_payload, str):
        # Handle both dict (from YAML) and string (fallback)
        try:
            auth_payload = json.loads(auth_payload)
        except json.JSONDecodeError:
            logger.error("Error: auth_payload in config.yaml is not valid JSON.")
            return None

    # If no payload provided in YAML, use defaults from .env
    payload: Dict[str, Any] = auth_payload or {
        "identity": os.getenv("NPM_IDENTITY"),
        "secret": os.getenv("NPM_SECRET")
    }

    try:
        response = requests.post(f"{url}/tokens", json=payload, timeout=DEFAULT_TIMEOUT)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error obtaining token from {url}: {e}")
        return None

    if not response.ok:
        logger.error(f"Authentication with {url} failed: {describe_http_failure(response)}")
        return None

    try:
        return response.json().get('token')
    except ValueError:
        logger.error(f"Authentication with {url} did not return JSON.")
        return None

def add_proxy_host(session: requests.Session, url: str, host_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Creates a new proxy host on the target NPM instance.
    """
    # Remove read-only or instance-specific fields from the source data
    payload: Dict[str, Any] = {k: v for k, v in host_config.items() if k not in EXCLUDED_KEYS}

    try:
        # NPM API endpoint for creating proxy hosts
        endpoint = f"{url}/nginx/proxy-hosts"
        logger.info(f"Creating proxy host with domains {payload.get('domain_names')} at {endpoint}")
        response = session.post(endpoint, json=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        logger.info(f"Successfully created proxy host: {payload.get('domain_names')}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"Network error creating host on {url}. Session invalidated.")
        session.headers.pop("Authorization", None) # Invalidate session
        logger.error(f"Failed to create proxy host {payload.get('domain_names')}: {e}")
        if e.response is not None:
            logger.error(f"API Error Detail: {e.response.text}")
        return None

def update_proxy_host(session: requests.Session, url: str, host_id: int, host_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Updates an existing proxy host on the target NPM instance.
    """
    # Remove read-only or instance-specific fields
    payload: Dict[str, Any] = {k: v for k, v in host_config.items() if k not in EXCLUDED_KEYS}

    try:
        # NPM API endpoint for updating is PUT /nginx/proxy-hosts/{id}
        endpoint = f"{url}/nginx/proxy-hosts/{host_id}"
        logger.info(f"Updating proxy host with domains {payload.get('domain_names')} at {endpoint}")
        response = session.put(endpoint, json=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        logger.info(f"Successfully updated proxy host: {payload.get('domain_names')}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"Network error updating host on {url}. Session invalidated.")
        session.headers.pop("Authorization", None) # Invalidate session
        logger.error(f"Failed to update proxy host {payload.get('domain_names')} (ID: {host_id}): {e}")
        if e.response is not None:
            logger.error(f"API Error Detail: {e.response.text}")
        return None

def delete_proxy_host(session: requests.Session, url: str, host_id: int, host_config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Deletes a proxy host from the target NPM instance.
    """
    # Determine domain names for logging if the config was provided
    domain_names: Any = host_config.get('domain_names') if host_config else "Unknown"

    try:
        # NPM API endpoint for deleting is DELETE /nginx/proxy-hosts/{id}
        endpoint = f"{url}/nginx/proxy-hosts/{host_id}"
        logger.info(f"Deleting proxy host with domains {domain_names} at {endpoint}")
        response = session.delete(endpoint, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        logger.info(f"Successfully deleted proxy host: {domain_names} (ID: {host_id})")
        return True
    except requests.exceptions.RequestException as e:
        logger.warning(f"Network error deleting host on {url}. Session invalidated.")
        session.headers.pop("Authorization", None) # Invalidate session
        logger.error(f"Failed to delete proxy host {domain_names} (ID: {host_id}): {e}")
        if e.response is not None:
            logger.error(f"API Error Detail: {e.response.text}")
        return False

def sync_to_target(source_hosts: List[Dict[str, Any]], session_t: requests.Session, target_url: str, dry_run: bool = False) -> bool:
    # Use sessions for better performance and cleaner header management
    try:
        # Get all hosts from target for comparison
        target_resp: requests.Response = session_t.get(f"{target_url}/nginx/proxy-hosts", timeout=DEFAULT_TIMEOUT)
        target_resp.raise_for_status()
        target_hosts: List[Dict[str, Any]] = target_resp.json()
        
        logger.info(f"Found {len(source_hosts)} hosts on source and {len(target_hosts)} on target.")

        # Create lookups using sorted domain tuples to handle variations in domain order
        source_lookup: Dict[tuple, Dict[str, Any]] = {tuple(sorted(h['domain_names'])): h for h in source_hosts}
        target_lookup: Dict[tuple, Dict[str, Any]] = {tuple(sorted(h['domain_names'])): h for h in target_hosts}

        # Phase 1: Delete hosts from target that don't exactly match a source domain set.
        # This frees up domain names that might be reassigned to different hosts,
        # preventing "domain already in use" errors during the creation/update phase.
        for target_tuple, target_host in target_lookup.items():
            if target_tuple not in source_lookup:
                if dry_run:
                    logger.info(f"[DRY RUN] Would delete host: {target_host['domain_names']}")
                else:
                    logger.info(f"Host with domains {target_host['domain_names']} no longer exists as a set in source. Deleting.")
                    delete_proxy_host(session_t, target_url, target_host['id'], target_host)

        # Phase 2: Add or Update remaining source hosts
        for source_tuple, source_host in source_lookup.items():
            if source_tuple in target_lookup:
                # Host with exact same domain set exists; update configuration
                target_host = target_lookup[source_tuple]
                if should_update(source_host, target_host):
                    if dry_run:
                        logger.info(f"[DRY RUN] Would update host: {source_host['domain_names']}")
                    else:
                        logger.info(f"Updating host with domains {source_host['domain_names']} (Target ID: {target_host['id']})")
                        update_proxy_host(session_t, target_url, target_host['id'], source_host)
                else:
                    logger.info(f"Host {source_host['domain_names']} is already up to date on target.")
            else:
                # New domain set found; create it
                if dry_run:
                    logger.info(f"[DRY RUN] Would create host: {source_host['domain_names']}")
                else:
                    logger.info(f"Creating host with domains {source_host['domain_names']} on target.")
                    add_proxy_host(session_t, target_url, source_host)
        
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during sync to target {target_url}: {e}")
        session_t.headers.pop("Authorization", None) # Invalidate session
        return False
    except Exception as e:
        logger.error(f"An error occurred during sync: {e}")
        return False

def should_update(source_host: Dict[str, Any], target_host: Dict[str, Any]) -> bool:
    """
    Compares key configuration fields to determine if an update is actually needed.
    This prevents unnecessary API calls and Nginx reloads.
    """
    relevant_keys: List[str] = [
        'forward_host', 'forward_port', 'forward_scheme', 
        'advanced_config', 'ssl_forced', 'http2_support',
        'block_exploits', 'caching_enabled', 'allow_websocket_upgrade', 
        'enabled'
    ]
    return any(source_host.get(key) != target_host.get(key) for key in relevant_keys)

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses the command line."""
    parser = argparse.ArgumentParser(
        description="This script synchronizes proxy hosts on a target Nginx server from a source Nginx server"
    )
    parser.add_argument(
        "-p", "--period", 
        type=int, 
        default=30,
        metavar="<SECONDS>", 
        help="Periodicity of the sync in seconds (default: 30)"
    )

    parser.add_argument(
        "-l", "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE"],
        type=str, 
        default="INFO",  # Use log.yaml config if not provided via CLI
        metavar="<LEVEL>", 
        help="Logging level (default: INFO)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a trial run with no changes made to target servers"
    )

    parser.add_argument(
        "--config-dir",
        metavar="<PATH>",
        help="Folder that holds config.yaml, log.yaml and .env (default: the folder "
             "of the nginx-sync binary, or of main.py when run from source)"
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help=f"Show the version recorded in {VERSION_FILE} and exit"
    )

    return parser.parse_args(argv)

# Set by the first Ctrl-C so further ones are swallowed (see _handle_sigint).
_STOP_REQUESTED = False

def _handle_sigint(signum: int, frame: Any) -> None:
    """
    Stops the sync loop on Ctrl-C and ignores every later Ctrl-C.

    PyInstaller's bootloader forwards the terminal's SIGINT to the program as
    well, so a single Ctrl-C arrives twice. Raising on both turned the second
    one into a traceback inside the shutdown code - and that could not be fixed
    by installing SIG_IGN there, because a signal that is already pending is
    still delivered before the next bytecode runs. Swallowing repeats here has
    no such window.
    """
    global _STOP_REQUESTED
    if _STOP_REQUESTED:
        return
    _STOP_REQUESTED = True
    raise KeyboardInterrupt

def run(args: argparse.Namespace) -> int:
    """Loads the configuration and runs the sync loop; returns an exit code."""
    load_settings(args.config_dir)

    if args.log_level != "NONE":
        logger.setLevel(args.log_level)

    # Fail immediately when an endpoint cannot log in, instead of retrying every
    # cycle and reporting the 400 that NPM returns for an incomplete payload.
    missing = missing_credentials()
    if missing:
        logger.error(f"No credentials configured for: {', '.join(missing)}")
        logger.error(
            f"Create {os.path.join(SETTINGS_DIR, '.env')} with NPM_IDENTITY and NPM_SECRET, "
            "or add auth_payload to that entry in config.yaml."
        )
        return 2

    main(period=args.period, dry_run=args.dry_run)
    return 0

def cli(argv: Optional[List[str]] = None) -> int:
    """Runs the command line interface and returns a process exit code."""
    args = parse_args(argv)

    # --version has to work without any configuration: it is what a service
    # manager or an upgrade script calls to see what it is about to run.
    if args.version:
        print(f"nginx-sync {read_version(args.config_dir)}")
        return 0

    # Ctrl-C is how the loop is normally stopped; see _handle_sigint.
    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        return run(args)
    except KeyboardInterrupt:
        logger.info("Sync process interrupted by user. Exiting gracefully.")
        return 130

if __name__ == "__main__":
    sys.exit(cli())
            
