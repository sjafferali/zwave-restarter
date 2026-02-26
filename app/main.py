"""
zwave-restarter: Monitors zwave-js-ui controller health and restarts when disconnected.
"""

import logging
import os
import sys
import time

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("zwave-restarter")

ZWAVE_URL = os.environ.get("ZWAVE_URL", "http://localhost:8091").rstrip("/")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "30"))
STARTUP_DELAY = int(os.environ.get("STARTUP_DELAY", "60"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "300"))


def is_controller_connected() -> bool | None:
    """Check if the zwave controller is connected via the health endpoint.

    Returns True if connected, False if disconnected, None if the request failed.
    """
    try:
        resp = requests.get(
            f"{ZWAVE_URL}/health/zwave",
            headers={"Accept": "text/plain"},
            timeout=REQUEST_TIMEOUT,
        )
        return resp.status_code == 200
    except requests.RequestException as e:
        log.warning("Failed to reach zwave-js-ui: %s", e)
        return None


def restart_controller() -> bool:
    """Issue a restart to the zwave-js-ui gateway. Returns True on success."""
    try:
        resp = requests.post(
            f"{ZWAVE_URL}/api/restart",
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                log.info("Restart successful: %s", data.get("message"))
                return True
            log.error("Restart returned failure: %s", data.get("message"))
            return False
        log.error("Restart request returned status %d", resp.status_code)
        return False
    except requests.RequestException as e:
        log.error("Failed to issue restart: %s", e)
        return False


def main() -> None:
    log.info("zwave-restarter starting")
    log.info("  ZWAVE_URL:       %s", ZWAVE_URL)
    log.info("  CHECK_INTERVAL:  %ds", CHECK_INTERVAL)
    log.info("  STARTUP_DELAY:   %ds", STARTUP_DELAY)

    if STARTUP_DELAY > 0:
        log.info("Waiting %ds for zwave-js-ui to initialize...", STARTUP_DELAY)
        time.sleep(STARTUP_DELAY)

    consecutive_failures = 0
    last_status_connected = None

    while True:
        status = is_controller_connected()

        if status is True:
            if last_status_connected is not True:
                log.info("Controller is connected")
            last_status_connected = True
            consecutive_failures = 0
        elif status is False:
            last_status_connected = False
            consecutive_failures += 1
            if consecutive_failures >= 2:
                log.warning("Controller DISCONNECTED for %d consecutive checks — issuing restart", consecutive_failures)
                restart_controller()
                consecutive_failures = 0
            else:
                log.warning("Controller is DISCONNECTED (%d/2 checks before restart)", consecutive_failures)
        else:
            log.warning("Could not determine controller status, skipping")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
