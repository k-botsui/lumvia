"""Maintainer-only build: no development software is needed on the receiving Mac."""

import argparse
import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "build/macos-cache"
LOCK = json.loads((Path(__file__).parent / "runtime-lock.json").read_text())


def command(args, cwd, env=None):
    print("Building:", Path(str(args[0])).name, flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def archive(name):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    entry = LOCK[name]
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".partial")
        command(
            [
                "/usr/bin/curl",
                "--fail",
                "--location",
                "--proto",
                "=https",
                "--tlsv1.2",
                "--retry",
                "3",
                "--output",
                str(temporary),
                entry["url"],
            ],
            ROOT,
        )
        temporary.replace(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise RuntimeError(f"Checksum mismatch: {name}")
    return path


def unpack(name, destination):
    destination.mkdir(parents=True, exist_ok=True)
    if not any(destination.iterdir()):
        with tarfile.open(archive(name)) as package:
            package.extractall(destination, filter="data")
    return next(p for p in destination.iterdir() if p.is_dir())


def fix_macho(root, arch):
    metadata_root = root.parent if root.name == "Contents" else root
    for attribute in ("com.apple.FinderInfo", "com.apple.ResourceFork"):
        subprocess.run(["xattr", "-dr", attribute, str(metadata_root)], capture_output=True, check=False)
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as file:
            magic = file.read(4)
        if magic not in {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}:
            continue
        # Replace the inode before editing previously executed signed code. macOS
        # caches signature pages and can kill tools that map an edited old inode.
        temporary = path.with_name(path.name + ".signing")
        shutil.copyfile(path, temporary)
        temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
        architectures = subprocess.check_output(["lipo", "-archs", str(path)], text=True).split()
        if arch not in architectures:
            raise RuntimeError(f"Wrong architecture: {path.name}")
        if len(architectures) > 1:
            command(["lipo", str(path), "-thin", arch, "-output", str(temporary)], ROOT)
            temporary.chmod(path.stat().st_mode & 0o777)
            temporary.replace(path)
        load = subprocess.check_output(["otool", "-l", str(path)], text=True)
        # LC_BUILD_VERSION/LC_VERSION_MIN_MACOSX only; dylib version numbers are unrelated.
        for block in re.split(r"Load command \d+", load):
            if "LC_BUILD_VERSION" in block or "LC_VERSION_MIN_MACOSX" in block:
                match = re.search(r"(?:minos|version)\s+(\d+(?:\.\d+)*)", block)
                if match and tuple(map(int, match.group(1).split(".")[:2])) > (12, 0):
                    raise RuntimeError(f"Monterey-incompatible binary: {path.name}: {match.group(1)}")
        dependencies = subprocess.check_output(["otool", "-L", str(path)], text=True).splitlines()[1:]
        identifiers = subprocess.check_output(["otool", "-D", str(path)], text=True).splitlines()[1:]
        library_id = identifiers[0] if identifiers else None
        edits = []
        for line in dependencies:
            dependency = line.strip().split(" (")[0]
            if dependency == library_id:
                continue
            if dependency.startswith(str(root) + "/"):
                target = Path(dependency)
                relative = os.path.relpath(target, path.parent)
                edits.extend(["-change", dependency, "@loader_path/" + relative])
            elif dependency.startswith("/") and not dependency.startswith(("/usr/lib/", "/System/Library/")):
                # Some upstream wheels retain build-time library IDs. Resolve only a
                # library actually shipped beside this binary; never search the host.
                candidates = [
                    path.parent / Path(dependency).name,
                    path.parent.parent / "lib" / Path(dependency).name,
                ]
                if "/Resources/runtime/" in dependency:
                    candidates.append(
                        root / "Resources/runtime" / dependency.split("/Resources/runtime/", 1)[1]
                    )
                target = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate.is_file() and candidate.resolve().is_relative_to(root.resolve())
                    ),
                    None,
                )
                if target is None:
                    raise RuntimeError(f"Unbundled dependency in {path.name}: {Path(dependency).name}")
                edits.extend(["-change", dependency, "@loader_path/" + os.path.relpath(target, path.parent)])
        if library_id and library_id.startswith("/"):
            edits.extend(["-id", "@loader_path/" + path.name])
        if edits:
            command(["install_name_tool", *edits, str(path)], ROOT)
        # Sign immediately after relocation, including wheel extensions.
        command(["codesign", "--force", "--sign", "-", str(path)], ROOT)


def license_inventory(packaged, source, notices):
    entries = []
    seen = set()
    for manifest in (packaged / "web").rglob("package.json"):
        data = json.loads(manifest.read_text())
        key = (data.get("name"), data.get("version"))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        entries.append(
            {"name": key[0], "version": key[1], "license": data.get("license", "See package notices")}
        )
        original = source / manifest.relative_to(packaged / "web")
        directory = notices / "JavaScript" / re.sub(r"[^A-Za-z0-9._-]", "_", "-".join(key))
        for path in original.parent.iterdir() if original.parent.exists() else []:
            if path.is_file() and path.name.lower().startswith(("license", "copying", "notice")):
                directory.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, directory / path.name)
    (notices / "JavaScript-dependencies.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2))


def build(arch, resume=False):
    if platform.system() != "Darwin":
        raise RuntimeError("Build on macOS")
    # Synced Desktop/Documents may add Finder metadata while signing. Build native
    # code outside those folders and avoid embedding a developer's home path.
    scratch = Path("/private/tmp") / f"lumvia-build-{os.getuid()}"
    scratch.mkdir(mode=0o700, exist_ok=True)
    if scratch.stat().st_uid != os.getuid() or scratch.is_symlink():
        raise RuntimeError("Build directory is not owned by this user")
    work = scratch / ("macos-" + arch)
    link = ROOT / "build" / ("macos-" + arch)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() and not link.is_symlink():
        raise RuntimeError("Move the previous build directory aside before using the isolated builder")
    if not link.is_symlink():
        link.symlink_to(work, target_is_directory=True)
    if work.exists() and not resume:
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    app = work / "Lumvia.app"
    contents = app / "Contents"
    resources = contents / "Resources"
    runtime = resources / "runtime"
    binaries = runtime / "bin"
    binaries.mkdir(parents=True, exist_ok=True)
    notices = resources / "ThirdParty"
    notices.mkdir(exist_ok=True)
    src = work / "source"
    src.mkdir(exist_ok=True)
    # Copy only the reviewed Git publication set. Never copy local .env or runtime state.
    for raw in subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0"):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        if (
            relative.parts[0] not in {"apps", "scripts", "packages"}
            or relative.parts[:2] == ("apps", "web")
            and "node_modules" in relative.parts
        ):
            continue
        target = src / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    node_name = next(
        name
        for name in LOCK
        if name.startswith("node-") and f"darwin-{'x64' if arch == 'x86_64' else 'arm64'}" in name
    )
    node = unpack(node_name, work / "node")
    shutil.copy2(node / "bin/node", binaries / "node")
    shutil.copy2(node / "LICENSE", notices / "Node-LICENSE.txt")
    python_name = next(
        name
        for name in LOCK
        if name.startswith("cpython-")
        and f"-{'x86_64' if arch == 'x86_64' else 'aarch64'}-" in name
        and name.endswith("install_only_stripped.tar.gz")
    )
    python = unpack(python_name, work / "python-download")
    if not (runtime / "python").exists():
        shutil.copytree(python, runtime / "python", symlinks=True)
    py = str(runtime / "python/bin/python3")
    environment = {
        **os.environ,
        "MACOSX_DEPLOYMENT_TARGET": "12.0",
        "CFLAGS": f"-O2 -arch {arch} -mmacosx-version-min=12.0",
        "LDFLAGS": f"-arch {arch} -mmacosx-version-min=12.0",
        "CC": f"clang -arch {arch}",
        "CXX": f"clang++ -arch {arch}",
        "RUSTFLAGS": f"--remap-path-prefix={Path.home()}=/build-home --remap-path-prefix={work}=/lumvia-build",
        "PATH": str(binaries) + ":" + os.environ["PATH"],
        "NEXT_TELEMETRY_DISABLED": "1",
        "LUMVIA_DESKTOP_BUILD": "1",
        "PYTHONNOUSERSITE": "1",
    }
    command(
        [py, "-m", "pip", "install", "--no-cache-dir", "-r", str(src / "apps/api/requirements.txt")],
        src,
        environment,
    )
    source_archives = work / "corresponding-source"
    source_archives.mkdir(exist_ok=True)
    for name in ("postgresql-17.9.tar.bz2", "valkey-9.1.2.tar.gz", "ffmpeg-8.1.tar.xz"):
        shutil.copy2(archive(name), source_archives / name)
    pg = unpack("postgresql-17.9.tar.bz2", work / "pg-source")
    command(
        [
            str(pg / "configure"),
            "--prefix=" + str(runtime / "postgres"),
            "--without-icu",
            "--without-readline",
            "--without-zlib",
            "--without-lz4",
            "--without-zstd",
            "--without-openssl",
        ],
        pg,
        environment,
    )
    command(["make", "-j4"], pg, environment)
    command(["make", "install"], pg, environment)
    shutil.copy2(pg / "COPYRIGHT", notices / "PostgreSQL-LICENSE.txt")
    valkey = unpack("valkey-9.1.2.tar.gz", work / "valkey-source")
    command(["make", "-j4", "MALLOC=libc", "BUILD_TLS=no", "USE_SYSTEMD=no"], valkey, environment)
    shutil.copy2(valkey / "src/valkey-server", binaries / "valkey-server")
    shutil.copy2(valkey / "COPYING", notices / "Valkey-LICENSE.txt")
    ffmpeg = unpack("ffmpeg-8.1.tar.xz", work / "ffmpeg-source")
    ff_flags = [
        "--prefix=" + str(runtime / "ffmpeg"),
        "--cc=clang",
        "--arch=" + arch,
        "--extra-cflags=" + environment["CFLAGS"],
        "--extra-ldflags=" + environment["LDFLAGS"],
        "--disable-autodetect",
        "--enable-videotoolbox",
        "--enable-audiotoolbox",
        "--enable-shared",
        "--disable-static",
        "--disable-gpl",
        "--disable-nonfree",
        "--disable-doc",
        "--disable-debug",
        "--disable-x86asm",
        "--disable-network",
    ]
    command([str(ffmpeg / "configure"), *ff_flags], ffmpeg, environment)
    command(["make", "-j4"], ffmpeg, environment)
    command(["make", "install"], ffmpeg, environment)
    for name in ("ffmpeg", "ffprobe"):
        (binaries / name).unlink(missing_ok=True)
        (binaries / name).symlink_to("../ffmpeg/bin/" + name)
    shutil.copy2(ffmpeg / "COPYING.LGPLv2.1", notices / "FFmpeg-LGPL-2.1.txt")
    (source_archives / "FFmpeg-build-options.json").write_text(
        json.dumps([flag.replace(str(runtime / "ffmpeg"), "$PREFIX") for flag in ff_flags], indent=2)
    )
    tooling = work / "tooling"
    command(
        [
            str(binaries / "node"),
            str(node / "lib/node_modules/npm/bin/npm-cli.js"),
            "install",
            "--prefix",
            str(tooling),
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            "pnpm@11.25.0",
        ],
        work,
        environment,
    )
    pnpm = [str(binaries / "node"), str(tooling / "node_modules/pnpm/bin/pnpm.cjs")]
    command([*pnpm, "install", "--frozen-lockfile"], src / "apps/web", environment)
    command([*pnpm, "build"], src / "apps/web", environment)
    packaged = resources / "app"
    if packaged.exists():
        shutil.rmtree(packaged)
    (packaged / "apps").mkdir(parents=True)
    shutil.copytree(
        src / "apps/api", packaged / "apps/api", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    (packaged / "scripts").mkdir()
    shutil.copy2(src / "scripts/bootstrap.py", packaged / "scripts/bootstrap.py")
    shutil.copytree(src / "apps/web/.next/standalone", packaged / "web", symlinks=True)
    shutil.copytree(src / "apps/web/.next/static", packaged / "web/apps/web/.next/static")
    shutil.copytree(src / "apps/web/public", packaged / "web/apps/web/public")
    # All app images use regular img elements. Do not redistribute the unused
    # Next image optimizer's native sharp/libvips dependency and additional LGPL libraries.
    for directory in (packaged / "web").rglob("node_modules"):
        direct = directory / "sharp"
        if direct.is_symlink():
            direct.unlink()
        store = directory / ".pnpm"
        if store.is_dir():
            for dependency in store.iterdir():
                if dependency.name.startswith(("sharp@", "@img+sharp-")):
                    shutil.rmtree(dependency)
    for dependency in (packaged / "web").rglob("*"):
        if dependency.is_symlink() and not dependency.exists():
            if "sharp" not in dependency.name:
                raise RuntimeError(f"Missing bundled module: {dependency.name}")
            dependency.unlink()
    license_inventory(packaged, src, notices)
    python_full_name = next(
        name
        for name in LOCK
        if name.endswith("-pgo+lto-full.tar.zst")
        and f"-{'x86_64' if arch == 'x86_64' else 'aarch64'}-" in name
    )
    license_dir = work / "python-licenses"
    license_dir.mkdir(exist_ok=True)
    command(
        [
            "/usr/bin/tar",
            "-xf",
            str(archive(python_full_name)),
            "-C",
            str(license_dir),
            "--include=python/licenses/*",
            "--include=python/PYTHON.json",
        ],
        work,
    )
    shutil.copytree(license_dir / "python/licenses", notices / "Python", dirs_exist_ok=True)
    shutil.copy2(license_dir / "python/PYTHON.json", notices / "Python-build-metadata.json")
    iconset = work / "Lumvia.iconset"
    iconset.mkdir(exist_ok=True)
    icon = src / "apps/web/public/brand/app-icon-512.png"
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            filename = f"icon_{size}x{size}" + ("@2x" if scale == 2 else "") + ".png"
            command(
                [
                    "sips",
                    "-z",
                    str(size * scale),
                    str(size * scale),
                    str(icon),
                    "--out",
                    str(iconset / filename),
                ],
                work,
            )
    command(["iconutil", "-c", "icns", str(iconset), "-o", str(resources / "Lumvia.icns")], work)
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, resources / name)
    shutil.copy2(Path(__file__).parent / "supervisor.py", resources / "supervisor.py")
    shutil.copy2(Path(__file__).parent / "runtime-lock.json", notices / "runtime-lock.json")
    (contents / "MacOS").mkdir(exist_ok=True)
    swift_source = work / "Lumvia.swift"
    shutil.copyfile(Path(__file__).parent / "Lumvia.swift", swift_source)
    command(
        [
            "swiftc",
            "-target",
            f"{arch}-apple-macos12.0",
            str(swift_source),
            "-o",
            str(contents / "MacOS/Lumvia"),
            "-framework",
            "AppKit",
            "-framework",
            "WebKit",
        ],
        ROOT,
    )
    plist = {
        "CFBundleExecutable": "Lumvia",
        "CFBundleIdentifier": "jp.lumvia.desktop",
        "CFBundleName": "Lumvia",
        "CFBundleIconFile": "Lumvia.icns",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
        "NSHumanReadableCopyright": "Copyright Lumvia. Personal noncommercial use only; third-party licenses apply separately.",
    }
    with (contents / "Info.plist").open("wb") as file:
        plistlib.dump(plist, file)
    for path in resources.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path)
    for directory in (
        runtime / "postgres/include",
        runtime / "postgres/lib/postgresql/pgxs",
        runtime / "postgres/lib/pkgconfig",
        runtime / "ffmpeg/include",
        runtime / "ffmpeg/lib/pkgconfig",
        runtime / "python/include",
    ):
        if directory.is_dir():
            shutil.rmtree(directory)
    # Lumvia uses PostgreSQL, not Berkeley DB/GDBM. Do not ship unused database
    # extensions with additional copyleft obligations.
    dynamic_modules = runtime / "python/lib/python3.13/lib-dynload"
    for pattern in ("_dbm.*", "_gdbm.*"):
        for module in dynamic_modules.glob(pattern):
            module.unlink()
    fix_macho(contents, arch)
    for path in resources.rglob("*"):
        if path.is_file() and not path.is_symlink() and str(Path.home()).encode() in path.read_bytes():
            raise RuntimeError(f"Developer home path found in distribution: {path.name}")
    command(["codesign", "--force", "--sign", "-", str(app)], ROOT)
    command(["codesign", "--verify", "--deep", "--strict", str(app)], ROOT)
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    label = "Intel" if arch == "x86_64" else "AppleSilicon"
    command(
        ["ditto", "-c", "-k", "--keepParent", str(app), str(output / f"Lumvia-Mac-{label}-TEST.zip")], ROOT
    )
    command(
        [
            "ditto",
            "-c",
            "-k",
            "--keepParent",
            str(source_archives),
            str(output / f"Lumvia-Mac-{label}-ThirdPartySource.zip"),
        ],
        ROOT,
    )
    print("Unsigned test build complete:", app)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", choices=["arm64", "x86_64"], default=platform.machine())
    parser.add_argument(
        "--resume", action="store_true", help="Reuse this architecture's private build directory"
    )
    args = parser.parse_args()
    build(args.arch, args.resume)
