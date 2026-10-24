"""Minimal Stingray Lua archive writer adapted from Bingus tooling."""
from __future__ import annotations

import struct

ARCHIVE_NAME = "9ba626afa44a3aa3.patch_0"
LUA_TYPE = 0xA14E8DFA2CD117E2
MASK64 = (1 << 64) - 1
MIX = 0xC6A4A7935BD1E995


def resource_hash(name: str) -> int:
    data = name.encode("utf-8")
    result = len(data) * MIX & MASK64
    complete = len(data) // 8 * 8
    for (word,) in struct.iter_unpack("<Q", data[:complete]):
        word = word * MIX & MASK64
        word ^= word >> 47
        result = (result ^ (word * MIX & MASK64)) * MIX & MASK64
    if complete != len(data):
        result = (result ^ int.from_bytes(data[complete:], "little")) * MIX & MASK64
    result ^= result >> 47
    result = result * MIX & MASK64
    return result ^ (result >> 47)


def lua_resource(body: bytes) -> bytes:
    return struct.pack("<II", len(body), 2) + body


def make_archive(resources: dict[int, bytes]) -> bytes:
    if not resources:
        raise ValueError("At least one Lua resource is required")
    count = len(resources)
    data_offset = (104 + 80 * count + 15) & ~15
    archive = bytearray(data_offset)
    entries = bytearray()
    for index, (name_hash, resource) in enumerate(sorted(resources.items())):
        entries.extend(struct.pack(
            "<7Q6I", name_hash, LUA_TYPE, data_offset, 0, 0, 0, 0,
            len(resource), 0, 0, 16, 16, index,
        ))
        archive.extend(resource)
        archive.extend(b"\0" * (-len(archive) % 16))
        data_offset = len(archive)
    header = struct.pack("<III20sQQ24s", 0xF0000011, 1, count, b"", data_offset, 0, b"")
    types = struct.pack("<IIQIIII", 0, 0, LUA_TYPE, count, 0, 16, 16)
    archive[:104 + len(entries)] = header + types + entries
    return bytes(archive)


def zip_files(path, files):
    import zipfile
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
