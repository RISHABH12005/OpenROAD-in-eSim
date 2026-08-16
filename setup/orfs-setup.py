#!/usr/bin/env python3

# =========================================================================
#          FILE: orfs-setup.py
#
#   DESCRIPTION: This file is used setup of orfs
#
#        AUTHOR: Rishabh Jain, 2r10j5@gmail.com
#    MAINTAINED: Sumanto Kar, sumantokar@iitb.ac.in
#  ORGANIZATION: eSim Team at FOSSEE, IIT Bombay
#       CREATED: Monday 2 March 2026
#      REVISION: Monday 3 Aug 2026
# =========================================================================

"""
orfs-setup.py — One-click installer for OpenROAD Flow Scripts (ORFS).

c
source, installs KLayout, and runs a verification test flow (GCD design).

Target:  Ubuntu 22.04 LTS  |  x86_64  |  Python 3.10+
Usage:   python3 orfs-setup.py [--force]
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Callable, Sequence

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
ORFS_DIR = BASE_DIR / "OpenROAD-flow-scripts"
TOOLS_DIR = ORFS_DIR / "tools"
INSTALL_DIR = TOOLS_DIR / "install"
FLOW_DIR = ORFS_DIR / "flow"
OPENROAD_BIN = INSTALL_DIR / "OpenROAD" / "bin" / "openroad"
YOSYS_BIN = INSTALL_DIR / "yosys" / "bin" / "yosys"
KEPLER_BIN = INSTALL_DIR / "kepler-formal" / "bin" / "kepler-formal"
ENV_SCRIPT = ORFS_DIR / "env.sh"
REPO_URL = "https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git"

LOG_DIR = BASE_DIR
INSTALL_LOG = LOG_DIR / "install.log"
DEP_LOG = LOG_DIR / "dependency.log"
BUILD_LOG = LOG_DIR / "build.log"
ERROR_LOG = LOG_DIR / "error.log"
SYSINFO_LOG = LOG_DIR / "system-info.log"
MANIFEST_FILE = BASE_DIR / "install-manifest.json"
VERSION_FILE = BASE_DIR / "version-manifest.json"

KLAYOUT_VER = "0.30.7"
KLAYOUT_URL = (
    f"https://www.klayout.org/downloads/Ubuntu-22.04/klayout_{KLAYOUT_VER}-1_amd64.deb"
)
KLAYOUT_CHECKSUM = "202530d198b0c7b93aa5af0e8e438ccd"
KLAYOUT_LOCAL_DEB = BASE_DIR.parent / "library" / "orfs" / f"klayout_{KLAYOUT_VER}-1_amd64.deb"

OR_TOOLS_VERSION_SMALL = "9.14.6206"
OR_TOOLS_VERSION_BIG = "9.14"
ABSL_VERSION = "20250512.0"
SWIG_REQUIRED = (4, 3, 0)
SWIG_TAG = "v4.3.0"
REQUIRED_PYTHON = (3, 8)

# ── ANSI colors ────────────────────────────────────────────────────────
class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    GRAY = "\033[90m"


def _c(color: str, msg: str) -> str:
    if sys.stdout.isatty():
        return f"{color}{msg}{Color.RESET}"
    return msg


# ── Logging setup ──────────────────────────────────────────────────────
_LOG_HANDLERS_INITIALIZED = False


def _setup_logging() -> None:
    global _LOG_HANDLERS_INITIALIZED
    if _LOG_HANDLERS_INITIALIZED:
        return
    _LOG_HANDLERS_INITIALIZED = True

    for p in [INSTALL_LOG, ERROR_LOG, DEP_LOG]:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setLevel(logging.INFO)
    stdout.setFormatter(fmt)
    root.addHandler(stdout)

    for log_file, level in [
        (INSTALL_LOG, logging.DEBUG),
        (ERROR_LOG, logging.ERROR),
    ]:
        fh = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        root.addHandler(fh)


log = logging.getLogger("orfs-setup")


# ── Helpers ────────────────────────────────────────────────────────────
class CommandError(RuntimeError):
    """Raised when a subprocess command fails after all retries."""


@dataclasses.dataclass
class InstallState:
    steps: list[str] = dataclasses.field(default_factory=list)
    errors: list[str] = dataclasses.field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    def start(self) -> None:
        self.start_time = time.time()

    def stop(self) -> None:
        self.end_time = time.time()

    def elapsed(self) -> str:
        if self.start_time == 0:
            return "0s"
        end = self.end_time or time.time()
        secs = int(end - self.start_time)
        if secs < 60:
            return f"{secs}s"
        return f"{secs // 60}m {secs % 60}s"

    def record_step(self, name: str) -> None:
        self.steps.append(f"[{datetime.datetime.now().isoformat()}] {name}")

    def record_error(self, msg: str) -> None:
        self.errors.append(f"[{datetime.datetime.now().isoformat()}] {msg}")


INSTALL_STATE = InstallState()

# ── Environment Isolation ──────────────────────────────────────────────


def _isolate_environment() -> None:
    log.info("Isolating build environment...")

    _detect_external_orfs_installations()
    _clear_orfs_env_vars()
    _purge_external_orfs_from_path()

    os.environ["OPENROAD"] = str(OPENROAD_BIN)
    os.environ["OPENROAD_EXE"] = str(OPENROAD_BIN)
    os.environ["YOSYS_EXE"] = str(YOSYS_BIN)
    os.environ["ORFS_ROOT"] = str(ORFS_DIR)
    os.environ["FLOW_HOME"] = str(FLOW_DIR)

    log.info("Environment isolated. OPENROAD=%s", OPENROAD_BIN)


def _detect_external_orfs_installations() -> None:
    known_paths = [
        Path.home() / "OpenROAD-flow-scripts",
        Path.home() / "Work" / "vlsi" / "tools" / "OpenROAD-flow-scripts",
        Path("/opt") / "OpenROAD-flow-scripts",
        Path("/usr/local") / "OpenROAD-flow-scripts",
        Path("/tmp") / "OpenROAD-flow-scripts",
    ]
    for p in known_paths:
        if p != ORFS_DIR and p.exists():
            log.warning("Found external ORFS installation at %s", p)


def _clear_orfs_env_vars() -> None:
    vars_to_clear = [
        "OPENROAD", "OPENROAD_EXE", "YOSYS_EXE", "FLOW_HOME",
        "ORFS_ROOT", "OPENROAD_BIN", "YOSYS_BIN",
    ]
    for var in vars_to_clear:
        if var in os.environ:
            val = os.environ.pop(var)
            log.warning("Cleared env var %s=%s", var, val)


def _purge_external_orfs_from_path() -> None:
    our_prefix = INSTALL_DIR.resolve()
    path_dirs = os.environ.get("PATH", "").split(":")
    cleaned = []
    purged = []
    for d in path_dirs:
        d_stripped = d.strip()
        if not d_stripped:
            continue
        try:
            p = Path(d_stripped).resolve()
            if our_prefix in p.parents:
                cleaned.append(d_stripped)
            else:
                for exe in ("openroad", "yosys", "sta", "kepler-formal"):
                    candidate = p / exe
                    if candidate.exists() and our_prefix not in candidate.resolve().parent.parents:
                        purged.append(d_stripped)
                        break
                else:
                    cleaned.append(d_stripped)
        except (ValueError, OSError, RuntimeError):
            cleaned.append(d_stripped)

    if purged:
        log.warning("Removed external ORFS paths from PATH: %s", "; ".join(purged))

    new_path = ":".join(cleaned)
    if new_path != os.environ.get("PATH", ""):
        os.environ["PATH"] = new_path
        log.info("PATH sanitized.")

    for exe in ("openroad", "yosys", "sta", "kepler-formal"):
        path = shutil.which(exe)
        if path:
            p = Path(path).resolve()
            if our_prefix not in p.parents:
                log.warning("External %s still in PATH at %s (may interfere)", exe, p)


def _verify_local_paths() -> None:
    our_prefix = INSTALL_DIR.resolve()
    for exe, expected in [
        ("openroad", OPENROAD_BIN),
        ("yosys", YOSYS_BIN),
        ("kepler-formal", KEPLER_BIN),
    ]:
        path = shutil.which(exe)
        if not path:
            log.info("%s not yet in PATH (will be configured after build)", exe)
            continue
        p = Path(path).resolve()
        expected_resolved = expected.resolve()
        if p != expected_resolved:
            log.error(
                "which %s → %s, but expected %s",
                exe, p, expected_resolved,
            )
            log.error("External %s may still be in PATH. Run: unset PATH && export PATH=/usr/bin:/bin", exe)
            continue
        log.info("%s → %s ✓", exe, path)


# ── Platform Detection ─────────────────────────────────────────────────
def _detect_platform() -> str:
    if not sys.platform.startswith("linux"):
        raise RuntimeError(f"Unsupported OS: {sys.platform}. Ubuntu 22.04 x86_64 required.")
    arch = platform.machine()
    if arch != "x86_64":
        raise RuntimeError(f"Unsupported architecture: {arch}. x86_64 required.")
    try:
        out = subprocess.run(
            ["lsb_release", "-si", "-sr"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        with open("/etc/os-release") as f:
            data = dict(
                l.strip().split("=", 1) for l in f if "=" in l
            )
        dist = data.get("ID", "").strip('"')
        ver = data.get("VERSION_ID", "").strip('"')
        out = f"{dist} {ver}"
    if "Ubuntu" not in out or "22.04" not in out:
        raise RuntimeError(
            f"Unsupported distribution: {out}. Ubuntu 22.04 LTS required."
        )
    return "ubuntu22.04"


def _system_info() -> dict[str, Any]:
    info: dict[str, Any] = {}
    info["platform"] = _detect_platform()
    info["hostname"] = platform.node()
    info["kernel"] = platform.release()
    info["cpu_count"] = os.cpu_count()
    try:
        out = subprocess.run(
            ["nproc", "--all"], capture_output=True, text=True
        ).stdout.strip()
        info["nproc"] = int(out) if out else info["cpu_count"]
    except Exception:
        info["nproc"] = info["cpu_count"]
    info["cpu_model"] = ""
    with open("/proc/cpuinfo") as f:
        for line in f:
            if line.startswith("model name"):
                info["cpu_model"] = line.split(":", 1)[1].strip()
                break
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    info["mem_total_kb"] = int(line.split()[1])
                    break
    except Exception:
        info["mem_total_kb"] = 0
    try:
        usage = shutil.disk_usage(BASE_DIR)
        info["disk_total_gb"] = round(usage.total / (1024 ** 3), 1)
        info["disk_free_gb"] = round(usage.free / (1024 ** 3), 1)
    except Exception:
        info["disk_total_gb"] = info["disk_free_gb"] = 0
    try:
        info["swap_total"] = subprocess.run(
            ["swapon", "--show", "--bytes"], capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        info["swap_total"] = ""
    info["python_version"] = sys.version
    for cc in ("gcc", "gcc-11", "gcc-12"):
        try:
            out = subprocess.run(
                [cc, "--version"], capture_output=True, text=True, timeout=10
            ).stdout
            info[f"{cc}_version"] = out.splitlines()[0] if out else ""
        except Exception:
            pass
    return info


def _suggest_threads(info: dict[str, Any] | None = None) -> int:
    if info is None:
        info = _system_info()
    total = info.get("nproc") or os.cpu_count() or 4
    mem_kb = info.get("mem_total_kb", 0)
    if mem_kb > 0:
        mem_gb = mem_kb / (1024 * 1024)
        by_mem = max(1, int(mem_gb / 2))
        threads = min(total, by_mem)
    else:
        threads = max(1, total - 1)
    return max(1, min(threads, 32))


def _log_system_info(info: dict[str, Any]) -> None:
    with open(SYSINFO_LOG, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, default=str)
    log.info(_c(Color.CYAN, "System Info"))
    log.info("  Platform   : %s", info.get("platform"))
    log.info("  CPU        : %s (%s cores)", info.get("cpu_model", "unknown"), info.get("cpu_count"))
    mem_gb = info.get("mem_total_kb", 0) / (1024 * 1024) if info.get("mem_total_kb") else 0
    log.info("  RAM        : %.1f GB", mem_gb)
    log.info("  Disk free  : %s GB", info.get("disk_free_gb"))
    log.info("  Swap       : %s", "enabled" if info.get("swap_total") else "none")
    log.info("  Build threads: %s", _suggest_threads(info))


# ── Subprocess ─────────────────────────────────────────────────────────
def _run(
    cmd: Sequence[str | os.PathLike[str] | Path],
    *,
    cwd: str | Path | None = None,
    timeout: int | None = None,
    retries: int = 0,
    retry_delay: int = 5,
    check: bool = True,
    verbose: bool = False,
    log_output: bool = True,
    env: dict[str, str] | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    cmd_str = " ".join(str(c) for c in cmd)
    cwd_str = str(cwd or Path.cwd())
    for attempt in range(1 + retries):
        if attempt > 0:
            log.warning(_c(Color.YELLOW, "Retry %d/%d for: %s"), attempt, retries, cmd_str)
            time.sleep(retry_delay)
        log.debug("[%s] %s", cwd_str, cmd_str)
        try:
            if verbose:
                result = subprocess.run(
                    [str(c) for c in cmd],
                    cwd=str(cwd) if cwd else None,
                    timeout=timeout,
                    env=env,
                    **kwargs,
                )
            else:
                result = subprocess.run(
                    [str(c) for c in cmd],
                    cwd=str(cwd) if cwd else None,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                    env=env,
                    **kwargs,
                )
                if log_output:
                    for line in (result.stdout or "").splitlines():
                        log.debug("  | %s", line)
                    for line in (result.stderr or "").splitlines():
                        log.debug("  ! %s", line)
        except subprocess.TimeoutExpired:
            log.error(_c(Color.RED, "Command timed out after %ds: %s"), timeout, cmd_str)
            if attempt < retries:
                continue
            raise CommandError(f"Timed out: {cmd_str}") from None
        except FileNotFoundError:
            log.error(_c(Color.RED, "Command not found: %s"), cmd_str)
            if attempt < retries:
                continue
            raise CommandError(f"Not found: {cmd_str}") from None
        except OSError as e:
            log.error(_c(Color.RED, "OS error running %s: %s"), cmd_str, e)
            if attempt < retries:
                continue
            raise CommandError(f"OS error: {cmd_str}: {e}") from None

        if result.returncode == 0:
            return result

        if verbose:
            log.error(_c(Color.RED, "Command failed (exit=%d): %s"), result.returncode, cmd_str)
        else:
            err_tail = (result.stdout or "")[-2000:]
            log.error(_c(Color.RED, "Command failed (exit=%d): %s\n%s"), result.returncode, cmd_str, err_tail)
        if attempt < retries:
            continue
        if check:
            raise CommandError(f"Exit {result.returncode}: {cmd_str}")
        return result

    raise AssertionError("unreachable")


def _sudo_run(
    cmd: Sequence[str | os.PathLike[str] | Path],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    return _run(["sudo"] + [str(c) for c in cmd], **kwargs)


def _check_executable(name: str) -> str | None:
    return shutil.which(name)


def _check_path(path: Path, desc: str) -> bool:
    if path.exists():
        return True
    log.error(_c(Color.RED, "%s not found: %s"), desc, path)
    return False


# ── APT Recovery & Install ─────────────────────────────────────────────
def _apt_recover() -> None:
    log.info("Repairing apt state...")
    for cmd in [
        ["sudo", "dpkg", "--configure", "-a"],
        ["sudo", "apt", "--fix-broken", "install", "-y"],
        ["sudo", "apt", "clean"],
        ["sudo", "apt", "autoremove", "-y"],
    ]:
        try:
            _run(cmd, check=False, verbose=True)
        except CommandError:
            pass
    _run(["sudo", "apt", "update"], verbose=True)


def _has_sudo() -> bool:
    result = subprocess.run(
        ["sudo", "-n", "true"], capture_output=True, text=True
    )
    return result.returncode == 0


def _ensure_sudo() -> None:
    log.info("Checking sudo access...")
    result = subprocess.run(
        ["sudo", "-n", "true"], capture_output=True, text=True
    )
    if result.returncode == 0:
        return
    log.warning(_c(Color.YELLOW, "Password-less sudo not available. Prompting for password..."))
    subprocess.run(
        ["sudo", "-v"], check=True,
    )
    log.info(_c(Color.GREEN, "Sudo access granted."))


# ── Dependency Installation ────────────────────────────────────────────
def _get_apt_packages() -> list[str]:
    return [
        "build-essential", "clang", "cmake", "git", "curl", "wget",
        "python3", "python3-pip", "python3-dev", "python3-venv",
        "bison", "flex", "swig", "tcl-dev",
        "libreadline-dev", "zlib1g-dev",
        "qtbase5-dev", "qtchooser", "qt5-qmake", "qtbase5-dev-tools",
        "libboost-all-dev", "libeigen3-dev", "libspdlog-dev", "libfmt-dev",
        "libomp-dev", "libffi-dev", "libtbb-dev", "xdot", "pkg-config", "ccache",
        "gcc-11", "g++-11", "make", "gawk",
        "libbz2-dev", "libyaml-cpp-dev", "libfl-dev", "libpcre2-dev",
        "libgomp1", "libgoogle-perftools-dev", "libgtest-dev",
        "qt5-image-formats-plugins",
        "automake", "autotools-dev", "pandoc", "unzip",
        "libtool", "autoconf", "libssl-dev", "liblzma-dev",
        "ruby", "ruby-dev",
        "python3-pandas", "python3-numpy", "python3-click", "python3-yaml",
        "time", "chrpath", "tcl-tclreadline", "libcapnp-dev",
    ]


def _install_apt_deps() -> None:
    log.info(_c(Color.CYAN, "Installing APT packages (%d packages)..."), len(_get_apt_packages()))
    packages = _get_apt_packages()
    with open(DEP_LOG, "a", encoding="utf-8") as log_f:
        log_f.write(f"\n--- APT packages ({time.ctime()}) ---\n")
        log_f.write(" ".join(packages) + "\n")

    batches = [packages[:10], packages[10:25], packages[25:]]
    for batch in batches:
        if not batch:
            continue
        _sudo_run(
            ["apt", "install", "-y", "--no-install-recommends"] + batch,
            verbose=True, retries=1,
        )
    log.info(_c(Color.GREEN, "APT packages installed."))


def _get_swig_version() -> tuple[int, ...]:
    swig = _check_executable("swig")
    if not swig:
        return ()
    try:
        r = subprocess.run(
            [swig, "-version"], capture_output=True, text=True, check=True
        )
        for line in r.stdout.splitlines():
            if "SWIG Version" in line:
                parts = line.split()[-1].split(".")
                return tuple(int(x) for x in parts)
    except Exception:
        pass
    return ()


def _install_swig_from_source() -> None:
    log.info("Building SWIG %s from source...", SWIG_TAG)
    src = Path("/tmp") / "swig-build"
    if src.exists():
        shutil.rmtree(src)
    _run(
        ["git", "clone", "--depth", "1", "--branch", SWIG_TAG,
         "https://github.com/swig/swig.git", str(src)],
        retries=1,
    )
    for cmd in [
        ["./autogen.sh"],
        ["./configure", "--prefix=/usr/local"],
    ]:
        _run(cmd, cwd=src, verbose=True, retries=1)
    jobs = _suggest_threads()
    _run(["make", f"-j{jobs}"], cwd=src, verbose=True, timeout=3600)
    _sudo_run(["make", "install"], cwd=src, verbose=True)
    _sudo_run(["rm", "-f", "/usr/bin/swig", "/usr/bin/swig4.0"])
    log.info(_c(Color.GREEN, "SWIG %s built and installed."), SWIG_TAG)


def _install_pip_deps() -> None:
    log.info("Installing Python pip packages...")
    lockfile = ORFS_DIR / "etc" / "requirements-common_lock.txt"
    if lockfile.exists():
        _sudo_run(
            ["pip3", "install", "--no-cache-dir", "-r", str(lockfile)],
            verbose=True, check=False,
        )
    else:
        log.warning("requirements lock file not found: %s", lockfile)


# ── KLayout ────────────────────────────────────────────────────────────
def _ensure_klayout() -> None:
    klayout_bin = Path("/usr/bin/klayout")
    if klayout_bin.exists():
        log.info("KLayout already installed: %s", klayout_bin)
        return

    log.info("Installing KLayout %s...", KLAYOUT_VER)
    deb_path: Path
    if KLAYOUT_LOCAL_DEB.exists():
        deb_path = KLAYOUT_LOCAL_DEB
        log.info("Using local .deb: %s", deb_path)
    else:
        deb_path = Path("/tmp") / f"klayout_{KLAYOUT_VER}-1_amd64.deb"
        log.info("Downloading KLayout from %s", KLAYOUT_URL)
        _run(["wget", "-q", "-O", str(deb_path), KLAYOUT_URL], verbose=True, retries=2)
        if KLAYOUT_CHECKSUM:
            r = _run(
                ["md5sum", str(deb_path)], capture_output=True, text=True, check=True
            )
            actual = r.stdout.split()[0]
            if actual != KLAYOUT_CHECKSUM:
                raise CommandError(
                    f"KLayout checksum mismatch: expected {KLAYOUT_CHECKSUM}, got {actual}"
                )
            log.info("KLayout checksum verified.")

    _sudo_run(["dpkg", "-i", str(deb_path)], check=False, verbose=True)
    _sudo_run(["apt", "install", "-f", "-y"], verbose=True)

    if not klayout_bin.exists():
        raise CommandError("KLayout installation failed despite dpkg+apt-fix.")
    log.info(_c(Color.GREEN, "KLayout %s installed successfully."), KLAYOUT_VER)


# ── Git / Clone / Update ──────────────────────────────────────────────
_REPO_CLONE_RETRIES = 2


def _clone_or_update_repo() -> None:
    log.info(_c(Color.CYAN, "Setting up OpenROAD-flow-scripts repository..."))

    if ORFS_DIR.exists():
        log.info("Removing existing ORFS directory for clean install...")
        shutil.rmtree(ORFS_DIR)

    log.info("Cloning repository (depth=1, branch=master)...")
    _run(
        ["git", "clone", "--depth", "1", "--branch", "master",
         REPO_URL, str(ORFS_DIR)],
        retries=_REPO_CLONE_RETRIES,
        verbose=True,
    )


def _init_submodules() -> None:
    log.info("Initializing git submodules...")
    _run(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=ORFS_DIR, retries=1, verbose=True,
    )


# ── Source Dependencies ────────────────────────────────────────────────
def _install_source_deps() -> None:
    log.info(_c(Color.CYAN, "Installing OpenROAD source dependencies..."))
    _init_submodules()

    dep_script = ORFS_DIR / "tools" / "OpenROAD" / "etc" / "DependencyInstaller.sh"
    if not dep_script.exists():
        log.warning("DependencyInstaller.sh not found at %s", dep_script)
        _fallback_source_deps()
        return

    jobs = _suggest_threads()
    log.info("Running OpenROAD DependencyInstaller (this may take 30-60 minutes)...")
    try:
        _sudo_run(
            [str(dep_script), "-common", f"-threads={jobs}"],
            cwd=ORFS_DIR, verbose=True, timeout=14400, retries=1,
        )
    except CommandError:
        log.warning("DependencyInstaller had errors, installing remaining deps manually...")
        _fallback_source_deps()

    _check_deps_after_install()


def _fallback_source_deps() -> None:
    jobs = _suggest_threads()
    _install_abseil_fallback(jobs)
    _install_ortools_fallback()


def _get_absl_version() -> str:
    candidates = [
        "/usr/local/lib/cmake/absl/abslConfigVersion.cmake",
        "/usr/local/lib64/cmake/absl/abslConfigVersion.cmake",
        "/usr/lib/cmake/absl/abslConfigVersion.cmake",
        "/usr/lib64/cmake/absl/abslConfigVersion.cmake",
        "/opt/or-tools/lib/cmake/absl/abslConfigVersion.cmake",
        "/opt/or-tools/lib64/cmake/absl/abslConfigVersion.cmake",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            for line in p.read_text().splitlines():
                m = re.match(r'.*PACKAGE_VERSION\s+"(.+)"', line)
                if m:
                    return m.group(1).rsplit(".", 1)[0]
    return ""


def _install_abseil_fallback(jobs: int) -> None:
    installed = _get_absl_version()
    required_base = ABSL_VERSION.rsplit(".", 1)[0]
    if installed == required_base:
        log.info("Abseil %s already installed.", installed)
        return

    log.info("Installing Abseil %s from source...", ABSL_VERSION)
    src = Path("/tmp") / "abseil-build"
    if src.exists():
        shutil.rmtree(src)
    _run(
        ["git", "clone", "--depth", "1", "--branch", ABSL_VERSION,
         "https://github.com/abseil/abseil-cpp.git", str(src)],
        retries=1,
    )
    cmake_bin = _check_executable("cmake")
    if not cmake_bin:
        raise CommandError("cmake not found after apt install.")
    _run(
        [cmake_bin, "-B", "build", "-S", ".",
         f"-DCMAKE_INSTALL_PREFIX=/usr/local",
         "-DCMAKE_CXX_STANDARD=17"],
        cwd=src, verbose=True,
    )
    _sudo_run(
        [cmake_bin, "--build", "build", "--target", "install", f"-j{jobs}"],
        cwd=src, verbose=True, timeout=3600,
    )
    log.info(_c(Color.GREEN, "Abseil %s installed."), ABSL_VERSION)


def _install_ortools_fallback() -> None:
    ortools_cfg = Path("/opt/or-tools/lib/cmake/ortools/ortoolsConfig.cmake")
    if ortools_cfg.exists():
        log.info("OR-Tools already installed.")
        return

    log.info("Downloading OR-Tools %s...", OR_TOOLS_VERSION_SMALL)
    file_name = f"or-tools_amd64_ubuntu-22.04_cpp_v{OR_TOOLS_VERSION_SMALL}.tar.gz"
    url = (
        f"https://github.com/google/or-tools/releases/download/"
        f"v{OR_TOOLS_VERSION_BIG}/{file_name}"
    )
    tmp = Path("/tmp") / file_name
    _run(["wget", "-q", "-O", str(tmp), url], retries=2, verbose=True)
    _sudo_run(["mkdir", "-p", "/opt/or-tools"])
    _sudo_run(
        ["tar", "--strip", "1", "--dir", "/opt/or-tools", "-xf", str(tmp)],
        verbose=True,
    )
    tmp.unlink(missing_ok=True)
    log.info(_c(Color.GREEN, "OR-Tools %s installed to /opt/or-tools."), OR_TOOLS_VERSION_SMALL)


def _check_deps_after_install() -> None:
    checks: dict[str, Path] = {
        "LEMON": Path("/usr/local/include/lemon/config.h"),
        "CUDD": Path("/usr/local/include/cudd.h"),
        "spdlog": Path("/usr/local/include/spdlog/version.h"),
    }
    missing = [name for name, p in checks.items() if not p.exists()]
    absl_ver = _get_absl_version()
    if absl_ver != "20250512":
        missing.append(f"Abseil (found {absl_ver or 'none'}, need 20250512)")
    if not _has_ortools():
        missing.append("OR-Tools")
    if missing:
        log.warning("Missing dependencies: %s", ", ".join(missing))
        log.warning("Build may fail. Attempting fallback install...")
        _fallback_source_deps()
        still_missing = [name for name, p in checks.items() if not p.exists()]
        if still_missing:
            log.warning("Still missing: %s", ", ".join(still_missing))
    else:
        log.info(_c(Color.GREEN, "All source dependencies verified."))


def _has_ortools() -> bool:
    candidates = [
        "/opt/or-tools/lib/cmake/ortools/ortoolsConfig.cmake",
        "/usr/local/lib/cmake/ortools/ortoolsConfig.cmake",
        "/usr/lib/cmake/ortools/ortoolsConfig.cmake",
    ]
    return any(Path(p).exists() for p in candidates)


# ── Swap ───────────────────────────────────────────────────────────────
def _ensure_swap() -> None:
    r = subprocess.run(["swapon", "--show"], capture_output=True, text=True)
    if r.stdout.strip():
        log.info("Swap already enabled.")
        return
    swapfile = Path("/swapfile")
    if swapfile.exists():
        log.info("/swapfile exists, activating...")
        _sudo_run(["mkswap", str(swapfile)], check=False)
        _sudo_run(["swapon", str(swapfile)], check=False)
    else:
        log.info("Creating 8 GB swap file...")
        if not _sudo_run(["fallocate", "-l", "8G", str(swapfile)], check=False).returncode == 0:
            _sudo_run(["dd", "if=/dev/zero", f"of={swapfile}", "bs=1M", "count=8192"],
                       verbose=True)
        _sudo_run(["chmod", "600", str(swapfile)])
        _sudo_run(["mkswap", str(swapfile)])
        _sudo_run(["swapon", str(swapfile)])
    fstab = Path("/etc/fstab")
    if fstab.exists():
        content = fstab.read_text()
        if "/swapfile" not in content:
            _sudo_run(
                ["sh", "-c", 'echo "/swapfile none swap sw 0 0" >> /etc/fstab'],
                verbose=True,
            )
    log.info("8 GB swap enabled.")


# ── Build ──────────────────────────────────────────────────────────────
def _build_tools() -> None:
    log.info(_c(Color.BOLD, "=" * 52))
    log.info(_c(Color.BOLD, "  BUILDING OPENROAD + YOSYS + KEPLER-FORMAL"))
    log.info(_c(Color.BOLD, "=" * 52))
    log.info("Build log: %s", BUILD_LOG)
    log.info("This may take 1-4 hours depending on hardware.")

    build_script = ORFS_DIR / "build_openroad.sh"
    if not build_script.exists():
        raise CommandError(f"build_openroad.sh not found: {build_script}")

    if not ORFS_DIR.exists():
        raise CommandError(f"ORFS directory missing: {ORFS_DIR}")
    os.chmod(str(build_script), build_script.stat().st_mode | stat.S_IEXEC)

    jobs = _suggest_threads()
    env = os.environ.copy()
    env["CC"] = "gcc-11"
    env["CXX"] = "g++-11"

    log.info("Starting build with %d threads...", jobs)
    with open(BUILD_LOG, "w", encoding="utf-8") as log_f:
        log_f.write(f"Build started: {time.ctime()}\n")
        log_f.write(f"Threads: {jobs}\n")
        log_f.write(f"CC: {env['CC']}, CXX: {env['CXX']}\n")
        log_f.write("-" * 60 + "\n")
        log_f.flush()
        result = subprocess.run(
            ["./build_openroad.sh", "--local", "--threads", str(jobs)],
            cwd=str(ORFS_DIR),
            text=True,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            env=env,
        )

    if result.returncode != 0:
        log.error(_c(Color.RED, "Build failed (exit=%d). Last 50 lines of %s:"),
                   result.returncode, BUILD_LOG)
        try:
            with open(BUILD_LOG) as f:
                lines = f.readlines()
                for line in lines[-50:]:
                    log.error("  %s", line.rstrip())
        except Exception:
            pass
        raise CommandError(
            f"Build failed. Check {BUILD_LOG} for details.\n"
            f"  tail -50 {BUILD_LOG}\n"
            f"To retry after fixing: cd {ORFS_DIR} && ./build_openroad.sh --local --threads {jobs}"
        )

    log.info(_c(Color.GREEN, "Build completed successfully."))


# ── Verification ───────────────────────────────────────────────────────
def _verify_openroad_binary() -> None:
    log.info(_c(Color.CYAN, "Verifying OpenROAD binary..."))
    if not _check_path(OPENROAD_BIN, "OpenROAD binary"):
        raise CommandError("OpenROAD binary not found")
    log.info("  Binary : %s", OPENROAD_BIN)
    log.info("  Size   : %.1f MB", OPENROAD_BIN.stat().st_size / (1024 * 1024))
    log.info("  Mode   : %s", stat.filemode(OPENROAD_BIN.stat().st_mode))
    _run([str(OPENROAD_BIN), "-version"], check=False)
    _run(["ldd", str(OPENROAD_BIN)], check=False)


def _verify_yosys_binary() -> None:
    log.info(_c(Color.CYAN, "Verifying Yosys binary..."))
    if not _check_path(YOSYS_BIN, "Yosys binary"):
        raise CommandError("Yosys binary not found")
    log.info("  Binary : %s", YOSYS_BIN)
    log.info("  Size   : %.1f MB", YOSYS_BIN.stat().st_size / (1024 * 1024))
    log.info("  Mode   : %s", stat.filemode(YOSYS_BIN.stat().st_mode))
    _run([str(YOSYS_BIN), "-V"], check=False)
    _run(["ldd", str(YOSYS_BIN)], check=False)


def _verify_kepler_binary() -> None:
    log.info(_c(Color.CYAN, "Verifying kepler-formal binary..."))
    if not _check_path(KEPLER_BIN, "kepler-formal binary"):
        raise CommandError("kepler-formal binary not found")
    log.info("  Binary : %s", KEPLER_BIN)
    log.info("  Size   : %.1f MB", KEPLER_BIN.stat().st_size / (1024 * 1024))
    _run([str(KEPLER_BIN), "--version"], check=False)


def _verify_tools() -> None:
    log.info(_c(Color.BOLD, "=" * 52))
    log.info(_c(Color.BOLD, "  TOOL VERIFICATION"))
    log.info(_c(Color.BOLD, "=" * 52))
    _verify_openroad_binary()
    _verify_yosys_binary()
    _verify_kepler_binary()
    log.info(_c(Color.GREEN, "All tools verified."))


def _configure_env() -> None:
    local_bin_dirs = [
        str(OPENROAD_BIN.parent),
        str(YOSYS_BIN.parent),
        str(KEPLER_BIN.parent),
    ]
    for d in local_bin_dirs:
        if d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{d}:{os.environ.get('PATH', '')}"

    os.environ["OPENROAD"] = str(OPENROAD_BIN)
    os.environ["OPENROAD_EXE"] = str(OPENROAD_BIN)
    os.environ["YOSYS_EXE"] = str(YOSYS_BIN)
    os.environ["FLOW_HOME"] = str(FLOW_DIR)
    os.environ["ORFS_ROOT"] = str(ORFS_DIR)

    or_path = shutil.which("openroad")
    ys_path = shutil.which("yosys")
    kp_path = shutil.which("kepler-formal")

    log.info(_c(Color.CYAN, "Environment Configuration"))
    log.info("  openroad   : %s", or_path)
    log.info("  yosys      : %s", ys_path)
    log.info("  kepler-formal: %s", kp_path)

    _verify_local_paths()
    log.info(_c(Color.GREEN, "Environment configured correctly."))


def _verify_env() -> None:
    if ENV_SCRIPT.exists():
        log.info("env.sh found: %s", ENV_SCRIPT)
    else:
        log.warning("env.sh not found (non-fatal)")


def _record_versions() -> dict[str, Any]:
    log.info(_c(Color.CYAN, "Recording version manifest..."))
    versions: dict[str, Any] = {
        "timestamp": datetime.datetime.now().isoformat(),
        "install_dir": str(INSTALL_DIR),
    }
    for name, path, ver_cmd in [
        ("OpenROAD", OPENROAD_BIN, ["-version"]),
        ("Yosys", YOSYS_BIN, ["-V"]),
        ("kepler-formal", KEPLER_BIN, ["--version"]),
    ]:
        if path.exists():
            try:
                r = subprocess.run(
                    [str(path)] + ver_cmd, capture_output=True, text=True, timeout=30
                )
                versions[name] = r.stdout.strip() or r.stderr.strip()
            except Exception as e:
                versions[name] = f"error: {e}"
        else:
            versions[name] = "not found"

    if ORFS_DIR.exists():
        try:
            r = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(ORFS_DIR), capture_output=True, text=True, timeout=30,
            )
            versions["orfs_git_commit"] = r.stdout.strip()
            r2 = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=str(ORFS_DIR), capture_output=True, text=True, timeout=30,
            )
            versions["orfs_git_message"] = r2.stdout.strip()
        except Exception as e:
            versions["orfs_git"] = f"error: {e}"

    versions["system"] = _system_info()

    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump(versions, f, indent=2, default=str)
    log.info("Version manifest written to %s", VERSION_FILE)
    return versions


def _write_manifest(versions: dict[str, Any]) -> None:
    manifest: dict[str, Any] = {
        "installer_version": "2.0",
        "install_path": str(BASE_DIR),
        "timestamp": datetime.datetime.now().isoformat(),
        "elapsed": INSTALL_STATE.elapsed(),
        "steps": INSTALL_STATE.steps,
        "errors": INSTALL_STATE.errors,
        "versions": versions,
        "system": _system_info(),
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    log.info("Install manifest written to %s", MANIFEST_FILE)


def _build_summary(versions: dict[str, Any]) -> None:
    print()
    print(_c(Color.BOLD, "=" * 60))
    print(_c(Color.BOLD, "  BUILD SUMMARY"))
    print(_c(Color.BOLD, "=" * 60))
    print(f"  Elapsed time : {INSTALL_STATE.elapsed()}")
    print(f"  Steps        : {len(INSTALL_STATE.steps)}")
    print(f"  Errors       : {len(INSTALL_STATE.errors)}")
    print()
    for name in ["OpenROAD", "Yosys", "kepler-formal"]:
        ver = versions.get(name, "unknown")
        print(f"  {name:15s}: {ver.split(chr(10))[0]}")
    print()
    if ORFS_DIR.exists():
        commit = versions.get("orfs_git_commit", "unknown")
        print(f"  ORFS Commit  : {commit[:16] if len(commit) > 16 else commit}")
    print(_c(Color.BOLD, "=" * 60))


# ── Test Flow ──────────────────────────────────────────────────────────
def _test_flow() -> None:
    log.info(_c(Color.BOLD, "=" * 52))
    log.info(_c(Color.BOLD, "  RUNNING GCD TEST FLOW"))
    log.info(_c(Color.BOLD, "=" * 52))

    if not FLOW_DIR.exists():
        raise CommandError(f"Flow directory missing: {FLOW_DIR}")

    test_config = FLOW_DIR / "designs" / "nangate45" / "gcd" / "config.mk"
    if not test_config.exists():
        log.warning("nangate45/gcd config not found at %s, skipping test.", test_config)
        return

    log.info("Cleaning previous results...")
    _run(["make", "clean_all"], cwd=FLOW_DIR, check=False, verbose=True, timeout=120)

    log.info("Running make DESIGN_CONFIG=./designs/nangate45/gcd/config.mk ...")
    result = subprocess.run(
        ["make", f"DESIGN_CONFIG=./designs/nangate45/gcd/config.mk"],
        cwd=str(FLOW_DIR),
        text=True,
        capture_output=True,
        timeout=14400,
    )
    for line in (result.stdout or "").splitlines():
        log.debug("  | %s", line)
    for line in (result.stderr or "").splitlines():
        log.debug("  ! %s", line)

    if result.returncode != 0:
        raise CommandError(
            f"GCD test flow failed (exit={result.returncode}).\n"
            f"Check {FLOW_DIR}/logs/ for details.\n"
            f"  cd {FLOW_DIR} && make DESIGN_CONFIG=./designs/nangate45/gcd/config.mk"
        )

    log.info(_c(Color.GREEN, "GCD test flow completed."))


def _verify_results() -> None:
    log.info(_c(Color.CYAN, "Verifying GCD flow results..."))
    result_dir = FLOW_DIR / "results" / "nangate45" / "gcd" / "base"
    if not result_dir.exists():
        log.warning("Results directory missing: %s", result_dir)
        return

    expected_files = ["6_final.def", "6_final.gds", "6_final.v", "6_final.sdc"]
    found: list[str] = []
    missing: list[str] = []
    for fname in expected_files:
        fp = result_dir / fname
        if fp.exists():
            found.append(fname)
            size = fp.stat().st_size
            log.info("  %-20s %10d bytes", fname, size)
        else:
            missing.append(fname)

    log.info("All files in %s:", result_dir)
    for f in sorted(result_dir.iterdir()):
        log.info("  - %s", f.name)

    if missing:
        log.warning("Missing expected files: %s", ", ".join(missing))

    if "6_final.def" in found and "6_final.gds" in found:
        log.info(_c(Color.GREEN, "DEF and GDS files confirmed — flow completed all stages."))
    else:
        log.warning("DEF/GDS output not found — flow may have partial results.")


# ── Retry ──────────────────────────────────────────────────────────────
def _retry_on_failure(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 2,
    retry_delay: int = 10,
    **kwargs: Any,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(1 + max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                log.warning(
                    _c(Color.YELLOW, "Attempt %d/%d failed for %s: %s"),
                    attempt + 1, max_retries + 1,
                    getattr(func, "__name__", str(func)),
                    e,
                )
                log.warning("Retrying in %d seconds...", retry_delay)
                time.sleep(retry_delay)
            else:
                log.error(
                    _c(Color.RED, "All %d attempts failed for %s."),
                    max_retries + 1,
                    getattr(func, "__name__", str(func)),
                )
                raise
    raise AssertionError("unreachable")


# ── Cleanup / Rollback ─────────────────────────────────────────────────
def _clean_before_install() -> None:
    log.info("Cleaning previous installation for fresh build...")

    dirs_to_remove = [ORFS_DIR]
    for d in dirs_to_remove:
        if d.exists():
            log.info("  Removing %s ...", d)
            shutil.rmtree(d)

    log.info("Cleanup complete.")


# ── Main ───────────────────────────────────────────────────────────────
def main() -> None:
    _setup_logging()
    INSTALL_STATE.start()

    force_rebuild = "--force" in sys.argv

    banner = textwrap.dedent(f"""\
    {_c(Color.CYAN, '=' * 52)}
    {_c(Color.BOLD, '  ORFS AUTOMATIC INSTALLER v2.0')}
    {_c(Color.CYAN, '=' * 52)}
      Install location : {BASE_DIR}
      Build log        : {BUILD_LOG}
      Error log        : {ERROR_LOG}
    """)
    print(banner)

    info = _system_info()
    _log_system_info(info)
    INSTALL_STATE.record_step("system_info")

    _isolate_environment()
    INSTALL_STATE.record_step("environment_isolated")

    if force_rebuild:
        _clean_before_install()
        INSTALL_STATE.record_step("clean_before_install")

    _ensure_sudo()
    INSTALL_STATE.record_step("sudo_verified")

    _apt_recover()
    INSTALL_STATE.record_step("apt_repaired")

    _install_apt_deps()
    INSTALL_STATE.record_step("apt_packages_installed")

    swig_ver = _get_swig_version()
    log.info("SWIG version detected: %s", ".".join(str(x) for x in swig_ver) if swig_ver else "not found")
    if swig_ver and swig_ver < SWIG_REQUIRED:
        _install_swig_from_source()
        INSTALL_STATE.record_step("swig_upgraded")
    elif not swig_ver:
        log.warning("SWIG not found — DependencyInstaller will handle it.")
    else:
        log.info("SWIG version %s meets requirement.", ".".join(str(x) for x in swig_ver))

    _ensure_swap()
    INSTALL_STATE.record_step("swap_ensured")

    _ensure_klayout()
    INSTALL_STATE.record_step("klayout_installed")

    _clone_or_update_repo()
    INSTALL_STATE.record_step("repo_cloned")

    _install_source_deps()
    INSTALL_STATE.record_step("source_deps_installed")

    _install_pip_deps()
    INSTALL_STATE.record_step("pip_deps_installed")

    _build_tools()
    INSTALL_STATE.record_step("tools_built")

    _verify_tools()
    INSTALL_STATE.record_step("tools_verified")

    versions = _record_versions()
    INSTALL_STATE.record_step("versions_recorded")

    _configure_env()
    INSTALL_STATE.record_step("environment_configured")

    _verify_env()
    INSTALL_STATE.record_step("env_verified")

    _retry_on_failure(_test_flow)
    INSTALL_STATE.record_step("test_flow_completed")

    _verify_results()
    INSTALL_STATE.record_step("results_verified")

    INSTALL_STATE.stop()
    _write_manifest(versions)
    _build_summary(versions)

    print()
    print(_c(Color.GREEN, "=" * 52))
    print(_c(Color.GREEN, _c(Color.BOLD, "  [SUCCESS] INSTALLATION COMPLETE")))
    print(_c(Color.GREEN, "=" * 52))
    print(f"  Tools       : {INSTALL_DIR}")
    print(f"  Env script  : source {ENV_SCRIPT}")
    print(f"  Elapsed     : {INSTALL_STATE.elapsed()}")
    print(f"  Manifest    : {MANIFEST_FILE}")
    print()


if __name__ == "__main__":
    main()
