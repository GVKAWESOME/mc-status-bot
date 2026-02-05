#!/usr/bin/env python3

"""
This software was sourced from Just-Some-Bots/MusicBot
Modified for Modern Python (3.10+) and discord.py 2.0+
"""

from __future__ import print_function

import os
import sys
import time
import logging
import traceback
import subprocess
from shutil import disk_usage, rmtree
from base64 import b64decode

try:
    import pathlib
    import importlib.util
except ImportError:
    pass

# Setup initial loggers
log = logging.getLogger("launcher")
log.setLevel(logging.DEBUG)

sh = logging.StreamHandler(stream=sys.stdout)
sh.setFormatter(logging.Formatter(fmt="[%(levelname)s] %(name)s: %(message)s"))

log.addHandler(sh)


class PIP(object):
    @classmethod
    def run(cls, command, check_output=False):
        if not cls.works():
            raise RuntimeError("Could not import pip.")
        try:
            return PIP.run_python_m(*command.split(), check_output=check_output)
        except subprocess.CalledProcessError as e:
            return e.returncode
        except Exception:
            traceback.print_exc()
            print("Error using -m method")

    @classmethod
    def run_python_m(cls, *args, **kwargs):
        check_output = kwargs.pop("check_output", False)
        check = subprocess.check_output if check_output else subprocess.check_call
        return check([sys.executable, "-m", "pip"] + list(args))

    @classmethod
    def run_install(cls, cmd, quiet=False, check_output=False):
        return cls.run("install %s%s" % ("-q " if quiet else "", cmd), check_output)

    @classmethod
    def works(cls):
        try:
            import pip
            return True
        except ImportError:
            return False


def bugger_off(msg="Press enter to continue . . .", code=1):
    input(msg)
    sys.exit(code)


def sanity_checks(optional=True):
    log.info("Starting sanity checks")
    
    # Required
    req_ensure_py3()
    req_ensure_encoding()
    req_ensure_env()
    req_ensure_folders()
    req_check_deps()

    log.info("Required checks passed.")

    if not optional:
        return

    opt_check_disk_space()
    log.info("Optional checks passed.")


def req_ensure_py3():
    log.info("Checking for Python 3.8+")
    
    # discord.py 2.0 requires 3.8+
    if sys.version_info < (3, 8):
        log.critical("Python 3.8+ is required. You are running %s", sys.version.split()[0])
        bugger_off()


def req_check_deps():
    try:
        import discord
        if discord.version_info.major < 2:
            log.warning(
                "This bot is designed for discord.py 2.0+. Your version is {0}. "
                "Things might break.".format(discord.__version__)
            )
    except ImportError:
        pass


def req_ensure_encoding():
    log.info("Checking console encoding")
    if (
        sys.platform.startswith("win")
        or sys.stdout.encoding.replace("-", "").lower() != "utf8"
    ):
        log.info("Setting console encoding to UTF-8")
        import io
        sys.stdout = io.TextIOWrapper(
            sys.stdout.detach(), encoding="utf8", line_buffering=True
        )
        sys.__stdout__ = sh.stream = sys.stdout


def req_ensure_env():
    log.info("Ensuring we're in the right environment")
    try:
        assert os.path.isfile("config.yml"), "config.yml file not found"
        assert os.path.isfile("bot.py"), "Could not find bot.py"
    except AssertionError as e:
        log.critical("Failed environment check, %s", e)
        bugger_off()

    try:
        os.mkdir("statusbot-test-folder")
    except Exception:
        log.critical("Current working directory does not seem to be writable")
        bugger_off()
    finally:
        if os.path.isdir("statusbot-test-folder"):
            rmtree("statusbot-test-folder", True)


def req_ensure_folders():
    pathlib.Path("logs").mkdir(exist_ok=True)
    pathlib.Path("data").mkdir(exist_ok=True)


def opt_check_disk_space(warnlimit_mb=200):
    if disk_usage(".").free < warnlimit_mb * 1024 * 2:
        log.warning(f"Less than {warnlimit_mb}MB of free space remains on this device")


def main():
    if "--no-checks" not in sys.argv:
        sanity_checks()

    tried_requirementstxt = False
    tryagain = True
    loops = 0
    max_wait_time = 60

    while tryagain:
        bot_instance = None
        try:
            # We import here to ensure fresh code on restart if possible
            from bot import ServerStatus
            
            # Initialize
            bot_instance = ServerStatus()
            
            # Run
            bot_instance.run()

        except SyntaxError:
            log.exception("Syntax error (this is a bug, not your fault)")
            break

        except ImportError:
            if not tried_requirementstxt:
                tried_requirementstxt = True
                log.exception("Error starting bot")
                log.info("Attempting to install dependencies...")
                err = PIP.run_install("--upgrade -r requirements.txt")
                if err:
                    log.critical("Could not auto-install dependencies.")
                    break
                else:
                    log.info("Dependencies installed. Retrying...")
                    continue
            else:
                log.exception("Unknown ImportError, exiting.")
                break

        except Exception as e:
            if "LoginFailure" in str(type(e)):
                log.exception("Login failed. Check your token in config.yml.")
                break
            else:
                log.exception("Error starting bot")

        finally:
            if not bot_instance or not bot_instance.init_ok:
                if any(sys.exc_info()):
                    traceback.print_exc()
                # If we didn't initialize, don't loop infinitely
                if loops > 2: 
                    break

            loops += 1

        # Check for restart signal if you implement a restart command
        # simplified here to just break if it crashed hard
        if not bot_instance or not getattr(bot_instance, "restart_signal", False):
            break

        sleeptime = min(loops * 2, max_wait_time)
        if sleeptime:
            log.info(f"Restarting in {sleeptime} seconds...")
            time.sleep(sleeptime)

    print()
    log.info("All done.")


if __name__ == "__main__":
    main()
