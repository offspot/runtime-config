#!/usr/bin/env python3

""" Toggle dnsmasq's spoof mode when internet connection is offline """

import argparse
import inspect
import pathlib
import re
import subprocess
import sys
from typing import Optional

parent = pathlib.Path(inspect.getfile(inspect.currentframe())).parent.resolve()
if parent not in sys.path:
    sys.path.insert(0, str(parent))

from configlib import (  # noqa: E402
    DNSMASQ_SPOOF_CONFIG_PATH,
    Config,
    __version__,
    ensure_folder,
    fail_error,
    get_progname,
    restart_service,
    succeed,
    warn_unless_root,
)

NAME = pathlib.Path(__file__).stem
INTERNET_STATUS_PATH = pathlib.Path("/var/run/internet")

Config.init(NAME)
logger = Config.logger


def toggle_dnsmasq(dnsmasq_conf_path: pathlib.Path, spoof: bool):
    """wether spoof file has been changed"""

    ensure_folder(dnsmasq_conf_path.parent)
    with open(dnsmasq_conf_path, "r") as fh:
        content = fh.read()

    is_spoof = False
    for line in content.splitlines():
        if line.startswith("address=/#/"):
            is_spoof = True
            break

    if (spoof and is_spoof) or (not spoof and not is_spoof):
        logger.info(f"already in correct mode: {is_spoof=} {spoof=}")
        return False

    logger.info(f"toggling from {is_spoof=} into {spoof=}")

    # turning non-spoof into spoof by removing comment on address
    if spoof and not is_spoof:
        for line in content.splitlines():
            m = re.match(r"^\s*#\s+(?P<line>address=/#/.+)$", line)
            if m:
                content = f"{m.groupdict()['line']}\n"
                break

    # turning spoof into non-spoof
    else:
        for line in content.splitlines():
            if line.startswith("address=/#/"):
                content = f"# {line}\n"
                break

    with open(dnsmasq_conf_path, "w") as fh:
        fh.write(content)

    return True


def restart_dnsmasq():
    return subprocess.run(["/usr/bin/systemctl", "restart", "dnsmasq"]).returncode == 0


def main(debug: Optional[bool] = False):
    warn_unless_root()

    spoof = False
    try:
        with open(INTERNET_STATUS_PATH, "r") as fh:
            status = fh.read().strip()
        spoof = status != "online"
    except Exception as exc:
        fail_error(
            f"unable to read Internet connection status "
            f"from {INTERNET_STATUS_PATH}: {exc}"
        )
    try:
        fixed = toggle_dnsmasq(dnsmasq_conf_path=DNSMASQ_SPOOF_CONFIG_PATH, spoof=spoof)
    except Exception as exc:
        fail_error(
            "unable to read/write dnsmasq spoof config "
            f"at {DNSMASQ_SPOOF_CONFIG_PATH}: {exc}"
        )
    if not fixed:
        return

    if restart_service("dnsmasq") != 0:
        fail_error("failed to restart dnsmasq")

    succeed("toggled spoof mode")


def entrypoint():
    parser = argparse.ArgumentParser(
        prog=get_progname(),
        description="Toggle dnsmasq's spoof mode based on internet connectivity",
    )
    parser.add_argument("-V", "--version", action="version", version=__version__)
    parser.add_argument("--debug", action="store_true", dest="debug")

    kwargs = dict(parser.parse_args()._get_kwargs())
    Config.set_debug(kwargs.get("debug"))

    try:
        sys.exit(main(**kwargs))
    except Exception as exc:
        if Config.debug:
            logger.exception(exc)
        else:
            logger.error(exc)
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
