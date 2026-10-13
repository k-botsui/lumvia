import importlib.util
from pathlib import Path


def test_wheel_path_remap_preserves_layout_and_leaves_other_paths_for_final_scan(tmp_path):
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("mac_build", root / "packaging/macos/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    site = tmp_path / "python/lib/python3.13/site-packages"
    site.mkdir(parents=True)
    upstream = b"/" + b"Users/runner"
    other_home = b"/" + b"Users/private-user"
    before = (
        b"\x00instructions\x00"
        + upstream
        + b"/work/pkg/source.c\x00"
        + upstream
        + b"/.cargo/registry/src/crate/lib.rs\x00"
        + other_home
        + b"/secret\x00END"
    )
    binary = site / "module.so"
    binary.write_bytes(before)
    source = site / "module.py"
    source.write_bytes(before)
    link = site / "linked.so"
    link.symlink_to(source)
    module.normalize_wheel_build_paths(tmp_path)
    after = binary.read_bytes()
    assert len(after) == len(before)
    assert after.startswith(b"\x00instructions\x00") and after.endswith(b"\x00END")
    assert upstream not in after and b"/build/worker/work/pkg/source.c" in after
    assert other_home in after
    assert source.read_bytes() == before and link.read_bytes() == before
