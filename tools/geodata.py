"""Merge native V2Ray geodata while preserving rule payloads and source names."""

from dataclasses import dataclass
import hashlib
import re


@dataclass(frozen=True)
class Field:
    number: int
    wire: int
    value: object
    raw: bytes


def read_varint(data, offset):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError("Truncated protobuf varint")
        byte = data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise ValueError("Protobuf varint overflows uint64")
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError("Invalid protobuf varint")


def varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def message_field(number, value):
    return varint(number << 3 | 2) + varint(len(value)) + value


def fields(data):
    offset = 0
    while offset < len(data):
        start = offset
        key, offset = read_varint(data, offset)
        number, wire = key >> 3, key & 7
        if not 0 < number < 1 << 29:
            raise ValueError("Invalid protobuf field number")
        if wire == 0:
            value, offset = read_varint(data, offset)
        elif wire == 2:
            size, offset = read_varint(data, offset)
            value = data[offset:offset + size]
            offset += size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value = data[offset:offset + size]
            offset += size
        else:
            raise ValueError("Unsupported protobuf wire type: " + str(wire))
        if offset > len(data):
            raise ValueError("Truncated protobuf field")
        yield Field(number, wire, value, data[start:offset])


@dataclass(frozen=True)
class Entry:
    name: str
    payload: bytes
    records: int

    def renamed(self, name):
        # Only country_code changes. Match types, attributes, regexps, CIDRs,
        # and unknown fields remain byte for byte identical to the source.
        payload = b"".join(
            message_field(1, name.upper().encode("ascii"))
            if (field.number, field.wire) == (1, 2) else field.raw
            for field in fields(self.payload)
        )
        return Entry(name.lower(), payload, self.records)


def read_entries(data, kind):
    if kind not in ("geosite", "geoip"):
        raise ValueError("Unknown geodata kind: " + kind)
    result = {}
    for field in fields(data):
        if (field.number, field.wire) != (1, 2):
            raise ValueError("Unexpected field in geodata list")
        name = None
        records = 0
        for part in fields(field.value):
            if (part.number, part.wire) == (1, 2):
                if name is not None:
                    raise ValueError("Duplicate country_code field")
                name = part.value.decode("ascii").lower()
            elif (part.number, part.wire) == (2, 2):
                record = {(item.number, item.wire): item.value for item in fields(part.value)}
                if kind == "geoip":
                    address, prefix = record.get((1, 2), b""), record.get((2, 0), 0)
                    if len(address) not in (4, 16) or not 0 <= prefix <= len(address) * 8:
                        raise ValueError("Invalid CIDR record")
                elif record.get((1, 0), 0) not in (0, 1, 2, 3) or not record.get((2, 2)):
                    raise ValueError("Invalid domain record")
                records += 1
            elif kind == "geoip" and (part.number, part.wire) == (3, 0) and part.value:
                raise ValueError("reverse_match=true is unsupported by Mihomo; refusing a semantic change")
        if not name or not re.fullmatch(r"[a-z0-9_!@.\-]+", name):
            raise ValueError("Invalid geodata category: " + repr(name))
        if name in result:
            raise ValueError("Duplicate geodata category: " + name)
        if not records:
            raise ValueError("Empty geodata category: " + name)
        result[name] = Entry(name, field.value, records)
    if not result:
        raise ValueError("Empty geodata file")
    return result


def merge(sources, aliases, kind):
    entries = {}
    catalog = []
    seen_sources = set()
    for source, data in sources:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", source) or source in seen_sources:
            raise ValueError("Invalid or duplicate source: " + source)
        seen_sources.add(source)
        original = read_entries(data, kind)
        for name, entry in sorted(original.items()):
            qualified = source + "-" + name
            if qualified in entries:
                raise ValueError("Category collision: " + qualified)
            entries[qualified] = entry.renamed(qualified)
            catalog.append({"name": qualified, "source": source, "category": name, "records": entry.records})
    for alias, target in sorted(aliases.items()):
        if not re.fullmatch(r"[a-z0-9_!@.\-]+", alias) or alias in entries:
            raise ValueError("Invalid or conflicting alias: " + alias)
        if target not in entries:
            raise ValueError("Alias target is missing: " + target)
        entries[alias] = entries[target].renamed(alias)
        catalog.append({"name": alias, "alias_of": target, "records": entries[target].records})
    if "cn" not in entries:
        raise ValueError("CN category is required for Mihomo geodata validation")
    output = b"".join(message_field(1, entries[name].payload) for name in sorted(entries))
    return output, sorted(catalog, key=lambda item: item["name"])


def digest(data):
    return hashlib.sha256(data).hexdigest()
