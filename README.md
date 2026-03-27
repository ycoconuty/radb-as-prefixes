radb-as-prefixes
Small CLI tool to fetch IPv4/IPv6 prefixes for an AS from RADb (IRRd !g / !6) and output them in various formats (plain, JSON, nftables set, ipset script).

No external whois, bash, grep, sort are required — only Python 3 with standard library (socket, ipaddress, argparse, json).

Features
Fetch prefixes from RADb by origin-AS via IRRd commands !gasN and !6asN.

IPv4, IPv6 or both families at once.

Collapse prefixes using Python’s ipaddress.collapse_addresses().

Output formats:

plain — one CIDR per line.

json — JSON array of CIDR strings.

nft-set — ready‑to‑include nftables set.

ipset — shell script with ipset create/flush/add commands.

Optional debug logging to file.

Usage
bash
./whois.py [AS] [options]
If AS is omitted, the tool will ask for it interactively (Enter AS (e.g. AS43515):).

Basic examples
Fetch both IPv4 and IPv6 prefixes (collapsed, plain text):

bash
./whois.py AS13335
Interactive input:

bash
./whois.py
# Enter AS (e.g. AS43515): AS13335
Address family flags
By default, both families are used: IPv4 + IPv6.

--ipv4 — IPv4 prefixes only.

--ipv6 — IPv6 prefixes only.

--ipv4 --ipv6 — same as default (both).

Examples:

bash
# IPv4 only
./whois.py AS13335 --ipv4

# IPv6 only
./whois.py AS13335 --ipv6
Output formats (--mode)
1) Plain text (default)
One CIDR per line:

bash
./whois.py AS13335
./whois.py AS13335 --ipv4
2) JSON array
bash
./whois.py AS13335 --mode json
./whois.py AS13335 --ipv4 --mode json
Output:

json
[
  "1.0.0.0/24",
  "1.1.1.0/24",
  "104.16.0.0/12",
  ...
]
3) nftables set (--mode nft-set)
Generate a set for nftables:

bash
./whois.py AS13335 --mode nft-set --set-name cf_as13335 > /etc/nft/cf_as13335.nft
Examples of types:

No --ipv4/--ipv6 (both families):

text
set cf_as13335 {
    type ip_addr
    flags interval
    elements = {
        1.0.0.0/24,
        1.1.1.0/24,
        ...
        2001:db8::/32
    }
}
IPv4 only:

bash
./whois.py AS13335 --ipv4 --mode nft-set --set-name cf_as13335_v4
→ type ipv4_addr.

IPv6 only:

bash
./whois.py AS13335 --ipv6 --mode nft-set --set-name cf_as13335_v6
→ type ipv6_addr.

Use it in an inet table:

text
table inet filter {
    include "/etc/nft/cf_as13335.nft"

    chain input {
        type filter hook input priority 0;
        ip saddr @cf_as13335 accept
        ip6 saddr @cf_as13335 accept
    }
}
4) ipset script (--mode ipset)
Generate ipset commands (for iptables or other tools):

bash
# IPv4 ipset
./whois.py AS13335 --ipv4 --mode ipset --set-name cf_as13335_v4 > cf_as13335_v4.sh
sh cf_as13335_v4.sh
Output:

text
ipset create cf_as13335_v4 hash:net family inet
ipset flush cf_as13335_v4
ipset add cf_as13335_v4 1.0.0.0/24
ipset add cf_as13335_v4 1.1.1.0/24
...
Rules example (iptables):

bash
iptables -A INPUT -m set --match-set cf_as13335_v4 src -j DROP
For IPv6:

bash
./whois.py AS13335 --ipv6 --mode ipset --set-name cf_as13335_v6
Note: for --mode ipset you must specify exactly one of --ipv4 or --ipv6.
If neither or both are given, the tool exits with an error.

Raw mode (--raw)
By default, prefixes are collapsed (aggregated). To get raw prefixes from RADb (validated, but not collapsed):

bash
# Raw, plain text
./whois.py AS13335 --raw

# Raw JSON
./whois.py AS13335 --raw --mode json

# Raw nft-set
./whois.py AS13335 --ipv4 --raw --mode nft-set --set-name cf_as13335_v4_raw
In --raw mode, the tool still validates prefixes via ipaddress, but does not aggregate them.

Logging (--logs)
Write debug logs to a file:

bash
./whois.py AS13335 --ipv4 --logs radb.log > prefixes.txt
prefixes.txt — only prefixes (stdout).

radb.log — debug lines like connection info, IRRd commands, counts, etc.

If the log file cannot be opened:

bash
./whois.py AS13335 --logs /root/radb.log
→ prints an error, exits with non‑zero code.

Error handling
Typical error cases:

Invalid AS format:

bash
./whois.py 13335
# stderr: AS number must be in the form AS12345
RADb unreachable / network issue:

bash
./whois.py AS13335
# stderr: failed to connect to ... or error during RADb exchange: ...
No prefixes for AS:

bash
./whois.py AS65535
# stderr: No prefixes found for AS65535 (after filtering/validation)
Wrong ipset usage:

bash
./whois.py AS13335 --mode ipset
# stderr: For --mode ipset you must specify exactly one of --ipv4 or --ipv6
All error messages go to stderr and the tool exits with a non‑zero status.

Requirements
Python 3 with:

socket

ipaddress

argparse

json

On OpenWrt this typically means installing at least:

text
opkg install python3-base python3-codecs python3-idna python3-light
(or the full python3 package, if space allows).
