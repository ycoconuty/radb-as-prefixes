#!/usr/bin/env python3
import argparse
import ipaddress
import json
import socket
import sys
from typing import Callable, List, Optional


RADB_HOST = "whois.radb.net"
RADB_PORT = 43
BUF_SIZE = 1024 * 8
SOCKET_TIMEOUT = 15


def make_logger(fp: Optional[Callable[[str], None]]) -> Callable[[str], None]:
    if fp is None:
        return lambda msg: None

    def _log(msg: str):
        try:
            fp(f"[LOG] {msg}\n")
        except OSError:
            pass

    return _log


def irrd_query(command: str, log: Callable[[str], None]) -> str:
    """
    Execute an IRRd command (!gasN / !6asN) against RADb and return the raw text response.
    """
    try:
        log(f"connecting to {RADB_HOST}:{RADB_PORT}")
        s = socket.create_connection((RADB_HOST, RADB_PORT), timeout=SOCKET_TIMEOUT)
    except OSError as e:
        raise RuntimeError(f"failed to connect to {RADB_HOST}:{RADB_PORT}: {e}")

    try:
        full_cmd = command + "\nq\n"
        log(f"sending command: {repr(full_cmd)}")
        s.sendall(full_cmd.encode())

        chunks = []
        total = 0
        while True:
            data = s.recv(BUF_SIZE)
            if not data:
                break
            chunks.append(data)
            total += len(data)
        log(f"received {total} bytes from RADb")
    except OSError as e:
        raise RuntimeError(f"error during RADb exchange: {e}")
    finally:
        try:
            s.close()
        except OSError:
            pass
        log("socket closed")

    if not chunks:
        raise RuntimeError("RADb returned an empty response")

    text = b"".join(chunks).decode(errors="ignore")
    log(f"first 200 bytes of response:\n{text[:200]!r}")
    return text


def get_prefix_tokens_for_family(asn: str, ipv6: bool, log: Callable[[str], None]) -> List[str]:
    """
    Fetch raw prefixes for a single address family (v4 or v6) via !gasN / !6asN.
    """
    asn = asn.upper()
    if not asn.startswith("AS"):
        raise ValueError("AS number must be in the form AS12345")

    num = asn[2:]
    cmd = f"!6as{num}" if ipv6 else f"!gas{num}"
    log(f"built IRRd command: {cmd}")

    text = irrd_query(cmd, log)
    lines = text.splitlines()
    log(f"total lines in response: {len(lines)}")

    tokens: List[str] = []
    for i, raw in enumerate(lines):
        line = raw.strip()
        log(f"line {i}: {raw!r}")
        if not line:
            continue

        # IRRd: 'A<length>' and 'C' are control lines.[web:20]
        if line.startswith("A") and line[1:].isdigit():
            continue
        if line == "C":
            continue

        for t in line.split():
            tokens.append(t)

    log(f"collected {len(tokens)} raw prefix tokens (ipv6={ipv6})")
    return tokens


def get_prefix_tokens_both_families(asn: str, want_v4: bool, want_v6: bool, log: Callable[[str], None]) -> List[str]:
    """
    Fetch raw prefixes for the required families:
    - no --ipv4/--ipv6: both v4 and v6 (default)
    - only --ipv4: v4
    - only --ipv6: v6
    - both flags: v4 + v6
    """
    tokens: List[str] = []

    if not want_v4 and not want_v6:
        v4 = get_prefix_tokens_for_family(asn, ipv6=False, log=log)
        v6 = get_prefix_tokens_for_family(asn, ipv6=True, log=log)
        tokens.extend(v4)
        tokens.extend(v6)
    else:
        if want_v4:
            tokens.extend(get_prefix_tokens_for_family(asn, ipv6=False, log=log))
        if want_v6:
            tokens.extend(get_prefix_tokens_for_family(asn, ipv6=True, log=log))

    if not tokens:
        raise RuntimeError("RADb returned no prefixes for this AS")
    return tokens


def parse_networks(tokens: List[str], want_v4: bool, want_v6: bool, log: Callable[[str], None]):
    """
    Convert string tokens into IPv4Network/IPv6Network objects,
    filtering by requested families (no collapsing).
    Returns (v4_list, v6_list).
    """
    v4_nets = []
    v6_nets = []

    for p in tokens:
        try:
            net = ipaddress.ip_network(p, strict=False)
        except ValueError:
            log(f"skip invalid token: {p!r}")
            continue

        if isinstance(net, ipaddress.IPv4Network):
            if want_v6 and not want_v4:
                continue
            v4_nets.append(net)
        else:
            if want_v4 and not want_v6:
                continue
            v6_nets.append(net)

    if not v4_nets and not v6_nets:
        log("no valid networks after parsing tokens")
    return v4_nets, v6_nets


def collapse_prefixes(tokens: List[str], want_v4: bool, want_v6: bool, log: Callable[[str], None]) -> List[str]:
    """
    Collapse prefixes by family:
    - only v4 or only v6: collapse that family
    - both: collapse v4 and v6 separately and concatenate the results
    """
    v4_nets, v6_nets = parse_networks(tokens, want_v4=want_v4, want_v6=want_v6, log=log)

    if not v4_nets and not v6_nets:
        return []

    result: List[str] = []

    if v4_nets:
        log(f"IPv4 networks before collapse: {len(v4_nets)}")
        v4_nets = sorted(set(v4_nets), key=lambda n: (int(n.network_address), n.prefixlen))
        log(f"IPv4 unique networks before collapse: {len(v4_nets)}")
        v4_collapsed = list(ipaddress.collapse_addresses(v4_nets))
        log(f"IPv4 networks after collapse: {len(v4_collapsed)}")
        result.extend(str(n) for n in v4_collapsed)

    if v6_nets:
        log(f"IPv6 networks before collapse: {len(v6_nets)}")
        v6_nets = sorted(set(v6_nets), key=lambda n: (int(n.network_address), n.prefixlen))
        log(f"IPv6 unique networks before collapse: {len(v6_nets)}")
        v6_collapsed = list(ipaddress.collapse_addresses(v6_nets))
        log(f"IPv6 networks after collapse: {len(v6_collapsed)}")
        result.extend(str(n) for n in v6_collapsed)

    return result


def output_plain(lines: List[str]):
    for p in lines:
        print(p)


def output_json(lines: List[str]):
    print(json.dumps(lines, indent=2, ensure_ascii=False))


def output_nft_set(prefixes: List[str], set_name: Optional[str], want_v4: bool, want_v6: bool):
    """
    Print an nftables set definition:
    - v4 only  → type ipv4_addr
    - v6 only  → type ipv6_addr
    - both     → type ip_addr (for inet tables)
    """
    if not set_name:
        set_name = "as_set"

    if want_v4 and not want_v6:
        addr_type = "ipv4_addr"
    elif want_v6 and not want_v4:
        addr_type = "ipv6_addr"
    else:
        addr_type = "ip_addr"

    print(f"set {set_name} {{")
    print(f"    type {addr_type}")
    print("    flags interval")
    print("    elements = {")
    for i, p in enumerate(prefixes):
        sep = "," if i < len(prefixes) - 1 else ""
        print(f"        {p}{sep}")
    print("    }")
    print("}")


def output_ipset(prefixes: List[str], set_name: Optional[str], want_v4: bool, want_v6: bool):
    """
    Print ipset commands.
    Exactly one of --ipv4/--ipv6 must be set.
    """
    if not set_name:
        set_name = "as_set"

    if want_v4 and not want_v6:
        family = "inet"
    elif want_v6 and not want_v4:
        family = "inet6"
    else:
        raise RuntimeError("For --mode ipset you must specify exactly one of --ipv4 or --ipv6")

    print(f"ipset create {set_name} hash:net family {family}")
    print(f"ipset flush {set_name}")
    for p in prefixes:
        print(f"ipset add {set_name} {p}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch IPv4/IPv6 prefixes by origin-AS from RADb (IRRd !g/!6)."
    )
    parser.add_argument(
        "asn",
        nargs="?",
        help="AS number, e.g. AS13335 (if omitted, will be asked interactively).",
    )
    parser.add_argument(
        "--ipv4",
        action="store_true",
        help="IPv4 prefixes only.",
    )
    parser.add_argument(
        "--ipv6",
        action="store_true",
        help="IPv6 prefixes only.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Do not collapse prefixes (no aggregation).",
    )
    parser.add_argument(
        "--logs",
        metavar="FILE",
        help="Write debug logs to FILE (no logs by default).",
    )
    parser.add_argument(
        "--mode",
        choices=["plain", "json", "nft-set", "ipset"],
        default="plain",
        help=(
            "Output format: "
            "plain (one CIDR per line), json (CIDR array), "
            "nft-set (nftables set), ipset (ipset commands)."
        ),
    )
    parser.add_argument(
        "--set-name",
        help="Set name for nftables/ipset (for --mode nft-set/ipset), e.g. cf_as13335_v4.",
    )

    args = parser.parse_args()

    want_v4 = args.ipv4
    want_v6 = args.ipv6

    asn = args.asn
    if not asn:
        try:
            asn = input("Enter AS (e.g. AS43515): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("AS is not specified", file=sys.stderr)
            sys.exit(1)
        if not asn:
            print("AS is not specified", file=sys.stderr)
            sys.exit(1)

    log_fp = None
    if args.logs:
        try:
            f = open(args.logs, "a", encoding="utf-8")
        except OSError as e:
            print(f"Failed to open log file {args.logs}: {e}", file=sys.stderr)
            sys.exit(1)

        def _fp(s: str, _f=f):
            _f.write(s)
            _f.flush()

        log_fp = _fp

    log = make_logger(log_fp)

    try:
        tokens = get_prefix_tokens_both_families(asn, want_v4=want_v4, want_v6=want_v6, log=log)
    except Exception as e:
        msg = f"Failed to fetch data from RADb for {asn}: {e}"
        print(msg, file=sys.stderr)
        if log_fp is not None:
            log(msg)
        sys.exit(1)

    # RAW mode (no collapse, but validated through ipaddress)
    if args.raw:
        v4_nets, v6_nets = parse_networks(tokens, want_v4=want_v4, want_v6=want_v6, log=log)
        lines: List[str] = [str(n) for n in v4_nets] + [str(n) for n in v6_nets]

        try:
            if args.mode == "json":
                output_json(lines)
            elif args.mode == "nft-set":
                output_nft_set(lines, args.set_name, want_v4=want_v4, want_v6=want_v6)
            elif args.mode == "ipset":
                output_ipset(lines, args.set_name, want_v4=want_v4, want_v6=want_v6)
            else:
                output_plain(lines)
        except Exception as e:
            print(f"Failed to format output: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Normal mode (with collapse)
    prefixes = collapse_prefixes(tokens, want_v4=want_v4, want_v6=want_v6, log=log)
    if not prefixes:
        msg = f"No prefixes found for {asn} (after filtering/validation)"
        print(msg, file=sys.stderr)
        if log_fp is not None:
            log(msg)
        sys.exit(1)
    try:
        if args.mode == "json":
            output_json(prefixes)
        elif args.mode == "nft-set":
            output_nft_set(prefixes, args.set_name, want_v4=want_v4, want_v6=want_v6)
        elif args.mode == "ipset":
            output_ipset(prefixes, args.set_name, want_v4=want_v4, want_v6=want_v6)
        else:
            output_plain(prefixes)
    except Exception as e:
        print(f"Failed to format output: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
