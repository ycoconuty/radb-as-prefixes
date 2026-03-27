# radb-as-prefixes

Small CLI tool to fetch IPv4/IPv6 prefixes for an AS from RADb (via IRRd `!g` / `!6`) and output them in various formats: plain text, JSON, nftables set, or ipset script. [web:1][web:8]

Only **Python 3** with the standard library is required (`socket`, `ipaddress`, `argparse`, `json`).

---

## Use cases
Automatically refresh AS prefixes and export them to JSON for use in Xray (e.g. routing rules based on specific ASNs).

Restrict SSH access to only the current GitHub address ranges by generating nftables/ipset rules from the GitHub AS prefixes, so that only GitHub Actions or other GitHub infrastructure can reach your SSH port for automated deployments/commits.

etc

---

## Why would I use this?

- You want to build dynamic firewall rules based on RADb data (per-AS rules). [web:8]  
- You run OpenWrt or a minimal system and do not want to install external whois/grep/sort utilities. [web:12]  
- You need repeatable, scriptable output formats (JSON, nftables, ipset) instead of ad-hoc whois parsing. [web:1][web:7]

---

## Features

- Fetch prefixes from RADb by origin-AS using IRRd commands `!gasN` and `!6asN`. [web:1][web:8]  
- Supports IPv4, IPv6, or both families at once.  
- Collapses (aggregates) prefixes via `ipaddress.collapse_addresses()`.  
- Output formats:
  - `plain` — one CIDR per line  
  - `json` — JSON array of CIDR strings  
  - `nft-set` — ready-to-include nftables set  
  - `ipset` — shell script for ipset [web:7][web:10]  
- Optional debug logging to file (`--logs`).

---

## Installation

Requires Python 3.

On OpenWrt, install:

```bash
opkg update
opkg install python3-base python3-codecs python3-idna python3-light
#or
opkg install python3
```

---

## Usage

```bash
./radb-as-prefixes.py [AS] [options]
```

If the AS is omitted, the tool will prompt for it interactively.

Examples:

```bash
# Both families (default)
./radb-as-prefixes.py AS13335

# Interactive input
./radb-as-prefixes.py
Enter AS (e.g. AS43515): AS13335
```

---

## Address family selection

By default, both IPv4 and IPv6 are used.

Flags:

```bash
--ipv4        # IPv4 only
--ipv6        # IPv6 only
--ipv4 --ipv6 # Same as default (both)
```

Examples:

```bash
./radb-as-prefixes.py AS13335 --ipv4
./radb-as-prefixes.py AS13335 --ipv6
```

---

## Output formats (`--mode`)

### 1. plain (default)

```bash
./radb-as-prefixes.py AS13335
```

Result: list of CIDR blocks, one per line.

---

### 2. json

```bash
./radb-as-prefixes.py AS13335 --mode json
```

Example output:

```json
["1.0.0.0/24", "1.1.1.0/24", "104.16.0.0/12", ...]
```

---

### 3. nft-set

Generate a ready-to-include nftables set:

```bash
./radb-as-prefixes.py AS13335 --mode nft-set --set-name cf_as13335 > /etc/nft/cf_as13335.nft
```

Example content:

```nft
set cf_as13335 {
    type ip_addr
    flags interval
    elements = { 1.0.0.0/24, 1.1.1.0/24, 2001:db8::/32 }
}
```

IPv4 only:

```bash
./radb-as-prefixes.py AS13335 --ipv4 --mode nft-set --set-name cf_as13335_v4
```

IPv6 only:

```bash
./radb-as-prefixes.py AS13335 --ipv6 --mode nft-set --set-name cf_as13335_v6
```

Use it in nftables:

```nft
table inet filter {
    include "/etc/nft/cf_as13335.nft"

    chain input {
        type filter hook input priority 0;
        ip saddr @cf_as13335 accept
        ip6 saddr @cf_as13335 accept
    }
}
```

---

### 4. ipset

Generate an ipset shell script:

```bash
./radb-as-prefixes.py AS13335 --ipv4 --mode ipset --set-name cf_as13335_v4 > cf_as13335_v4.sh
sh cf_as-prefixes_v4.sh
```

Example:

```bash
ipset create cf_as13335_v4 hash:net family inet
ipset flush cf_as13335_v4
ipset add cf_as13335_v4 1.0.0.0/24
ipset add cf_as13335_v4 1.1.1.0/24
...
```

Important: for `--mode ipset` you must specify exactly one of `--ipv4` or `--ipv6`; if neither or both are given, the tool exits with an error. [web:7][web:10]

---

## Raw mode (`--raw`)

In raw mode the tool prints non-collapsed prefixes (still validated, but not aggregated).

Examples:

```bash
# Raw plain text
./radb-as-prefixes.py AS13335 --raw

# Raw JSON
./radb-as-prefixes.py AS13335 --raw --mode json

# Raw nftables set for IPv4
./radb-as-prefixes.py AS13335 --ipv4 --raw --mode nft-set --set-name cf_as13335_v4_raw
```

---

## Logging

To write debug logs to a file:

```bash
./radb-as-prefixes.py AS13335 --ipv4 --logs radb.log > prefixes.txt
```

- `prefixes.txt` — prefixes only (stdout)  
- `radb.log` — connection details, IRRd commands, counters, etc.

If the log file cannot be opened:

```bash
./radb-as-prefixes.py AS13335 --logs /root/radb.log
stderr: cannot open log file ...
```

---

## Error handling

Typical cases:

| Description        | Example                                        | Message                                     |
|--------------------|------------------------------------------------|---------------------------------------------|
| Invalid AS format  | `./radb-as-prefixes.py 13335`                  | `AS number must be in the form AS12345`     |
| RADb unreachable   | `./radb-as-prefixes.py AS13335`                | `failed to connect to ...`                  |
| No prefixes for AS | `./radb-as-prefixes.py AS65535`                | `No prefixes found for AS65535`             |
| Wrong ipset usage  | `./radb-as-prefixes.py AS13335 --mode ipset`   | `must specify exactly one of --ipv4/--ipv6` |

All error messages go to **stderr**, and the tool exits with a non-zero status code.

---

## License

This project is licensed under the MIT License.  
See the `LICENSE` file for details.
