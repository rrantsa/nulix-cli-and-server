#!/usr/bin/env python3
"""Train the Nulix knowledge base with 300 diverse Linux intents.

For each intent the script:
1. Searches the KB
2. Checks whether the top-ranked template matches the expected command
3. If wrong or missing, inserts a corrected rule into the KB

Run:
    python3 scripts/train_kb.py [--db /opt/nulix/knowledge.db]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from knowledge import KnowledgeBase

# ───────────────────────────────────────────────────────────────────
# 300 intents — each is (natural_language, expected_command_template, category)
# ───────────────────────────────────────────────────────────────────
INTENTS: list[tuple[str, str, str]] = [
    # ══════════════════════════════════════════════════════════════
    # FILES — 80 intents
    # ══════════════════════════════════════════════════════════════
    ("list files in current directory", "ls", "files"),
    ("list files in home directory", "ls ~", "files"),
    ("show me what is in this folder", "ls", "files"),
    ("list all files including hidden and dotfiles", "ls -la", "files"),
    ("show hidden dot files in long format", "ls -la", "files"),
    ("list files with sizes in human readable format", "ls -lh", "files"),
    ("list files sorted by modification time newest first", "ls -lt", "files"),
    ("list files sorted by size largest first", "ls -lS", "files"),
    ("list files in reverse order", "ls -lr", "files"),
    ("list only directories in current folder", "ls -d */", "files"),
    ("list files recursively in all subdirectories", "ls -R", "files"),
    ("show a tree view of the directory structure", "tree {directory}", "files"),
    ("tree view two levels deep", "tree -L {depth} {directory}", "files"),
    ("find all files bigger than 100 megabytes", "find {directory} -type f -size +{size}", "files"),
    ("find files smaller than 1 kilobyte", "find {directory} -type f -size -{size}", "files"),
    ("search for files named config.yaml", "find {directory} -name '{pattern}'", "files"),
    ("find all log files anywhere on the system", "find / -name '*.log'", "files"),
    ("find files modified in the last 24 hours", "find {directory} -type f -mtime -{days}", "files"),
    ("find files not modified in the last 7 days", "find {directory} -type f -mtime +{days}", "files"),
    ("find all empty files in a directory tree", "find {directory} -type f -empty", "files"),
    ("find all empty directories", "find {directory} -type d -empty", "files"),
    ("find files owned by a specific user", "find {directory} -user {username}", "files"),
    ("find files with specific permission bits set", "find {directory} -perm {mode}", "files"),
    ("find all executable files in a tree", "find {directory} -type f -executable", "files"),
    ("find files newer than a reference file", "find {directory} -newer {reference}", "files"),
    ("find all symlinks in a directory", "find {directory} -type l", "files"),
    ("count how many files are in a directory tree", "find {directory} -type f | wc -l", "files"),
    ("count total number of directories recursively", "find {directory} -type d | wc -l", "files"),
    ("find and delete all .tmp files", "find {directory} -name '{pattern}' -delete", "files"),
    ("find files and execute a command on each one", "find {directory} -name '{pattern}' -exec {command} {} \\;", "files"),
    ("find files containing specific text in their name", "find {directory} -name '{pattern}'", "files"),
    ("find files by extension recursively", "find {directory} -name '*.{ext}'", "files"),
    ("find all python source files", "find {directory} -name '*.py'", "files"),
    ("find all javascript files", "find {directory} -name '*.js'", "files"),
    ("find all markdown documentation files", "find {directory} -name '*.md'", "files"),
    ("find configuration yaml files", "find {directory} -name '*.yaml' -o -name '*.yml'", "files"),
    ("copy a file to another location", "cp {source} {destination}", "files"),
    ("copy a directory and all its contents recursively", "cp -r {source} {destination}", "files"),
    ("copy preserving file permissions and timestamps", "cp -p {source} {destination}", "files"),
    ("copy multiple files into a target directory", "cp {files} {directory}", "files"),
    ("copy files interactively asking before overwrite", "cp -i {source} {destination}", "files"),
    ("move a file to another directory", "mv {source} {destination}", "files"),
    ("rename a file giving it a new name", "mv {old_name} {new_name}", "files"),
    ("move all log files to a backup folder", "mv *.log {directory}", "files"),
    ("delete a single file", "rm {file}", "files"),
    ("remove a file permanently", "rm {file}", "files"),
    ("delete multiple files matching a pattern", "rm {pattern}", "files"),
    ("delete a directory and everything inside it", "rm -rf {directory}", "files"),
    ("remove an empty directory", "rmdir {directory}", "files"),
    ("create a new directory", "mkdir {directory}", "files"),
    ("create a folder", "mkdir {directory}", "files"),
    ("create nested directories making parent dirs as needed", "mkdir -p {path}", "files"),
    ("create a directory with specific permissions", "mkdir -m {mode} {directory}", "files"),
    ("change permissions of a file to read write execute for owner only", "chmod 700 {file}", "files"),
    ("make a file readable writable by owner and group", "chmod 660 {file}", "files"),
    ("make a file readable by everyone", "chmod 644 {file}", "files"),
    ("make a script executable", "chmod +x {file}", "files"),
    ("remove execute permission from a file", "chmod -x {file}", "files"),
    ("change permissions recursively on a directory", "chmod -R {mode} {directory}", "files"),
    ("change the owner of a file", "chown {user} {file}", "files"),
    ("change both owner and group of a file", "chown {user}:{group} {file}", "files"),
    ("change group ownership of a directory recursively", "chgrp -R {group} {directory}", "files"),
    ("create a symbolic link to a file", "ln -s {target} {link_name}", "files"),
    ("create a hard link to a file", "ln {target} {link_name}", "files"),
    ("show what type a file is", "file {path}", "files"),
    ("check the mime type of a file", "file --mime-type {path}", "files"),
    ("show the size of a file or directory", "du -sh {path}", "files"),
    ("show disk usage of current directory", "du -sh .", "files"),
    ("show disk usage of first level subdirectories sorted by size", "du -h --max-depth=1 {directory} | sort -rh", "files"),
    ("show free disk space on all mounted filesystems", "df -h", "files"),
    ("show available inodes on each filesystem", "df -i", "files"),
    ("create a tar gzip archive of a directory", "tar -czf {archive}.tar.gz {directory}", "files"),
    ("create a tar bzip2 compressed archive", "tar -cjf {archive}.tar.bz2 {directory}", "files"),
    ("extract a tar gzip file", "tar -xzf {archive}.tar.gz", "files"),
    ("extract a tar archive to a specific directory", "tar -xzf {archive}.tar.gz -C {directory}", "files"),
    ("list contents of a tar file without extracting", "tar -tzf {archive}.tar.gz", "files"),
    ("compress a directory into a zip file", "zip -r {archive}.zip {directory}", "files"),
    ("extract a zip archive", "unzip {archive}.zip", "files"),
    ("list contents of a zip file without extracting", "unzip -l {archive}.zip", "files"),
    ("compare two files line by line showing differences", "diff {file1} {file2}", "files"),
    ("compare two directories recursively", "diff -r {dir1} {dir2}", "files"),
    ("show unified diff between two files", "diff -u {file1} {file2}", "files"),

    # ══════════════════════════════════════════════════════════════
    # TEXT — 45 intents
    # ══════════════════════════════════════════════════════════════
    ("search for a string recursively in all files under a directory", "grep -r '{pattern}' {directory}", "text"),
    ("grep for a word in files ignoring case", "grep -ri '{pattern}' {directory}", "text"),
    ("search for whole words only with grep", "grep -rw '{pattern}' {directory}", "text"),
    ("show line numbers with grep matches", "grep -rn '{pattern}' {directory}", "text"),
    ("grep and show context lines around each match", "grep -rC {n} '{pattern}' {directory}", "text"),
    ("invert grep match showing lines not containing pattern", "grep -v '{pattern}' {file}", "text"),
    ("count how many lines match a pattern", "grep -c '{pattern}' {file}", "text"),
    ("grep for lines starting with a specific string", "grep '^{pattern}' {file}", "text"),
    ("grep for lines ending with a specific string", "grep '{pattern}$' {file}", "text"),
    ("search recursively in python files only", "grep -r '{pattern}' {directory} --include='*.py'", "text"),
    ("search recursively excluding a directory", "grep -r '{pattern}' {directory} --exclude-dir={skip}", "text"),
    ("count number of lines in a file", "wc -l {file}", "text"),
    ("count number of words in a file", "wc -w {file}", "text"),
    ("count number of characters in a file", "wc -c {file}", "text"),
    ("show the first 10 lines of a file", "head {file}", "text"),
    ("show the first N lines of a file", "head -n {count} {file}", "text"),
    ("show the last 10 lines of a file", "tail {file}", "text"),
    ("show the last N lines of a file", "tail -n {count} {file}", "text"),
    ("follow a log file tailing new lines as they appear", "tail -f {file}", "text"),
    ("follow a log file and keep trying if file is not accessible", "tail -F {file}", "text"),
    ("sort lines of a file alphabetically", "sort {file}", "text"),
    ("sort lines in reverse alphabetical order", "sort -r {file}", "text"),
    ("sort lines numerically", "sort -n {file}", "text"),
    ("sort by the second column of a file", "sort -k2 {file}", "text"),
    ("sort a file and remove duplicate lines", "sort -u {file}", "text"),
    ("remove duplicate adjacent lines", "uniq {file}", "text"),
    ("count occurrences of each unique line", "uniq -c {file}", "text"),
    ("show only duplicate lines", "uniq -d {file}", "text"),
    ("find most frequent lines in a text file", "sort {file} | uniq -c | sort -rn", "text"),
    ("replace all occurrences of a string in a file", "sed -i 's/{old}/{new}/g' {file}", "text"),
    ("replace text inline in a file with sed", "sed -i 's/{old}/{new}/g' {file}", "text"),
    ("replace only the first occurrence on each line", "sed -i 's/{old}/{new}/' {file}", "text"),
    ("delete lines matching a pattern from a file", "sed -i '/{pattern}/d' {file}", "text"),
    ("print a specific line number from a file with sed", "sed -n '{n}p' {file}", "text"),
    ("find and replace across all files of a type in a directory", "find {dir} -name '*.{ext}' -exec sed -i 's/{old}/{new}/g' {} +", "text"),
    ("cut out specific columns from a delimited file", "cut -d'{delim}' -f{fields} {file}", "text"),
    ("cut the first field from a colon separated file", "cut -d: -f1 {file}", "text"),
    ("extract specific characters by position from each line", "cut -c{range} {file}", "text"),
    ("translate characters replacing one set with another", "tr '{set1}' '{set2}' < {file}", "text"),
    ("convert lowercase to uppercase in a file", "tr '[:lower:]' '[:upper:]' < {file}", "text"),
    ("squeeze repeated characters into a single one", "tr -s '{char}' < {file}", "text"),
    ("use awk to print a specific column from a file", "awk '{print ${n}}' {file}", "text"),
    ("use awk to sum values in a column", "awk '{sum += ${n}} END {print sum}' {file}", "text"),
    ("use awk to filter lines where a column matches a condition", "awk '${n} {op} {value}' {file}", "text"),
    ("use awk to print lines longer than a minimum length", "awk 'length > {n}' {file}", "text"),

    # ══════════════════════════════════════════════════════════════
    # PROCESSES — 30 intents
    # ══════════════════════════════════════════════════════════════
    ("list all running processes with details", "ps aux", "processes"),
    ("show every process on the system", "ps aux", "processes"),
    ("list processes in a tree format showing parent child relationships", "ps auxf", "processes"),
    ("show processes for a specific user only", "ps -u {username}", "processes"),
    ("list processes sorted by CPU usage highest first", "ps aux --sort=-%cpu", "processes"),
    ("list processes sorted by memory usage highest first", "ps aux --sort=-%mem", "processes"),
    ("show the top 10 cpu consuming processes", "ps aux --sort=-%cpu | head -11", "processes"),
    ("show top memory hungry processes", "ps aux --sort=-%mem | head -11", "processes"),
    ("find a process by its name", "ps aux | grep {name}", "processes"),
    ("check if a specific program is running", "pgrep {name}", "processes"),
    ("find the PID of a running program by name", "pgrep {name}", "processes"),
    ("kill a process by its process ID", "kill {pid}", "processes"),
    ("terminate a process gracefully by pid", "kill {pid}", "processes"),
    ("force kill a process that is not responding", "kill -9 {pid}", "processes"),
    ("kill a process by its name", "pkill {name}", "processes"),
    ("kill all instances of a program", "pkill {name}", "processes"),
    ("kill processes matching a pattern", "pkill -f '{pattern}'", "processes"),
    ("send a specific signal to a process", "kill -{signal} {pid}", "processes"),
    ("list all available signals", "kill -l", "processes"),
    ("show process tree hierarchy", "pstree", "processes"),
    ("show process tree for a specific user", "pstree {username}", "processes"),
    ("run a command in the background", "{command} &", "processes"),
    ("run a command immune to hangups with nohup", "nohup {command} &", "processes"),
    ("bring a background job to the foreground", "fg", "processes"),
    ("list background jobs in the current shell", "jobs", "processes"),
    ("resume a stopped background job", "bg", "processes"),
    ("change the priority of a running process", "renice {priority} -p {pid}", "processes"),
    ("start a program with a specific niceness priority", "nice -n {priority} {command}", "processes"),
    ("interactive process viewer showing real time cpu and memory", "top", "processes"),
    ("interactive process viewer in a terminal with color", "htop", "processes"),

    # ══════════════════════════════════════════════════════════════
    # NETWORKING — 40 intents
    # ══════════════════════════════════════════════════════════════
    ("show all listening TCP ports on the system", "ss -tlnp", "networking"),
    ("show listening UDP ports", "ss -ulnp", "networking"),
    ("show all network connections established and listening", "ss -tunap", "networking"),
    ("show network interfaces with their IP addresses", "ip addr show", "networking"),
    ("show just the ip addresses assigned to interfaces", "ip -br addr show", "networking"),
    ("show the routing table", "ip route show", "networking"),
    ("show the default gateway", "ip route show default", "networking"),
    ("show link layer information for network interfaces", "ip link show", "networking"),
    ("display network interface statistics", "ip -s link", "networking"),
    ("bring a network interface up", "ip link set {interface} up", "networking"),
    ("bring a network interface down", "ip link set {interface} down", "networking"),
    ("test connectivity to a remote host with ping", "ping -c {count} {host}", "networking"),
    ("ping a host indefinitely until stopped", "ping {host}", "networking"),
    ("trace the route packets take to a destination", "traceroute {host}", "networking"),
    ("resolve a domain name to an IP address", "dig +short {domain}", "networking"),
    ("lookup all DNS records for a domain", "dig {domain} ANY", "networking"),
    ("query a specific DNS record type like MX or TXT", "dig {domain} {type}", "networking"),
    ("reverse DNS lookup from IP to hostname", "dig -x {ip_address}", "networking"),
    ("perform a DNS lookup using a specific nameserver", "dig @{server} {domain}", "networking"),
    ("download a file from a URL", "curl -O {url}", "networking"),
    ("download a file and save it with a specific name", "curl -o {filename} {url}", "networking"),
    ("download a file following redirects", "curl -L -O {url}", "networking"),
    ("send a GET request and show response headers", "curl -I {url}", "networking"),
    ("send a POST request with JSON data", "curl -X POST -H 'Content-Type: application/json' -d '{data}' {url}", "networking"),
    ("download a file with wget", "wget {url}", "networking"),
    ("download a whole website recursively with wget", "wget --mirror --convert-links {url}", "networking"),
    ("test if a TCP port is open on a remote server", "nc -zv {host} {port}", "networking"),
    ("scan a range of ports on a remote host", "nc -zv {host} {start_port}-{end_port}", "networking"),
    ("listen on a TCP port and print received data", "nc -l {port}", "networking"),
    ("check what program is listening on a specific port", "ss -tlnp | grep :{port}", "networking"),
    ("show the public IP address of this server", "curl -s ifconfig.me", "networking"),
    ("show the public IP using an alternative service", "curl -s icanhazip.com", "networking"),
    ("show network bandwidth usage in real time", "iftop", "networking"),
    ("monitor network traffic on a specific interface", "tcpdump -i {interface}", "networking"),
    ("capture network packets to a file for later analysis", "tcpdump -i {interface} -w {file}", "networking"),
    ("show active network connections and the programs using them", "ss -tunap", "networking"),
    ("show the ARP table IP to MAC address mapping", "ip neigh show", "networking"),
    ("show multicast group memberships", "ip maddr show", "networking"),
    ("check the SSL certificate expiration date for a website", "echo | openssl s_client -servername {host} -connect {host}:443 2>/dev/null | openssl x509 -noout -dates", "networking"),
    ("download a file over SSH from a remote server", "scp {user}@{host}:{remote_path} {local_path}", "networking"),

    # ══════════════════════════════════════════════════════════════
    # SYSTEM — 45 intents
    # ══════════════════════════════════════════════════════════════
    ("show how much memory is used and free", "free -h", "system"),
    ("show memory usage in megabytes", "free -m", "system"),
    ("show the system load average and uptime", "uptime", "system"),
    ("show how long the system has been running", "uptime", "system"),
    ("show the kernel version and architecture", "uname -r", "system"),
    ("show all system information from uname", "uname -a", "system"),
    ("show operating system name and version", "cat /etc/os-release", "system"),
    ("show CPU architecture and model information", "lscpu", "system"),
    ("show block devices and partition layout", "lsblk", "system"),
    ("show block devices with filesystem information", "lsblk -f", "system"),
    ("show PCI devices connected to the system", "lspci", "system"),
    ("show USB devices connected to the system", "lsusb", "system"),
    ("show hardware information summary", "lshw -short", "system"),
    ("show the current date and time", "date", "system"),
    ("show the date in ISO 8601 format", "date -Iseconds", "system"),
    ("display the system hostname", "hostname", "system"),
    ("set the system hostname", "hostnamectl set-hostname {name}", "system"),
    ("show systemd service status", "systemctl status {service}", "system"),
    ("check if a service is running", "systemctl is-active {service}", "system"),
    ("start a systemd service", "systemctl start {service}", "system"),
    ("stop a systemd service", "systemctl stop {service}", "system"),
    ("restart a systemd service", "systemctl restart {service}", "system"),
    ("reload a systemd service configuration", "systemctl reload {service}", "system"),
    ("enable a service to start automatically at boot", "systemctl enable {service}", "system"),
    ("disable a service from starting at boot", "systemctl disable {service}", "system"),
    ("list all systemd units and their states", "systemctl list-units", "system"),
    ("list all failed systemd units", "systemctl --failed", "system"),
    ("show journal logs for a specific service following new entries", "journalctl -u {service} -f", "system"),
    ("show journal logs since the last boot", "journalctl -b", "system"),
    ("show the most recent journal entries", "journalctl -n {count}", "system"),
    ("show journal logs from the previous boot", "journalctl -b -1", "system"),
    ("show kernel messages from the current boot", "dmesg", "system"),
    ("show kernel messages with human readable timestamps", "dmesg -T", "system"),
    ("show the last kernel messages tail", "dmesg | tail", "system"),
    ("reboot the system", "reboot", "system"),
    ("shutdown the system now", "shutdown now", "system"),
    ("shutdown the system at a specific time", "shutdown {time}", "system"),
    ("cancel a pending shutdown", "shutdown -c", "system"),
    ("list all timers for systemd scheduled tasks", "systemctl list-timers", "system"),
    ("show the current runlevel or boot target", "systemctl get-default", "system"),
    ("change the default boot target to multi-user", "systemctl set-default multi-user.target", "system"),
    ("show currently loaded kernel modules", "lsmod", "system"),
    ("load a kernel module", "modprobe {module}", "system"),
    ("remove a kernel module", "modprobe -r {module}", "system"),
    ("show information about a kernel module", "modinfo {module}", "system"),

    # ══════════════════════════════════════════════════════════════
    # USERS — 20 intents
    # ══════════════════════════════════════════════════════════════
    ("show the username of the current user", "whoami", "users"),
    ("show who is logged into the system", "who", "users"),
    ("show detailed information about logged in users", "w", "users"),
    ("show the user ID group ID and groups for a user", "id {username}", "users"),
    ("show what groups the current user belongs to", "groups", "users"),
    ("list all user accounts on the system", "cat /etc/passwd | cut -d: -f1", "users"),
    ("create a new user account with a home directory", "useradd -m {username}", "users"),
    ("create a new user with a specific shell", "useradd -m -s {shell} {username}", "users"),
    ("delete a user account but keep their home directory", "userdel {username}", "users"),
    ("delete a user account and remove their home directory", "userdel -r {username}", "users"),
    ("change the password for a user", "passwd {username}", "users"),
    ("lock a user account preventing login", "passwd -l {username}", "users"),
    ("unlock a user account", "passwd -u {username}", "users"),
    ("add an existing user to a supplementary group", "usermod -aG {group} {username}", "users"),
    ("create a new group", "groupadd {group}", "users"),
    ("delete a group", "groupdel {group}", "users"),
    ("list all groups on the system", "cat /etc/group | cut -d: -f1", "users"),
    ("switch to another user account with their environment", "su - {username}", "users"),
    ("run a single command as another user", "sudo -u {username} {command}", "users"),
    ("run a command as root with sudo", "sudo {command}", "users"),

    # ══════════════════════════════════════════════════════════════
    # PACKAGES (apt/debian) — 15 intents
    # ══════════════════════════════════════════════════════════════
    ("update the apt package index", "apt update", "packages"),
    ("upgrade all installed packages to latest versions", "apt upgrade -y", "packages"),
    ("install a package using apt", "apt install -y {package}", "packages"),
    ("remove a package using apt", "apt remove -y {package}", "packages"),
    ("completely remove a package including configuration files", "apt purge -y {package}", "packages"),
    ("search for available packages by keyword", "apt search {keyword}", "packages"),
    ("show detailed information about a package", "apt show {package}", "packages"),
    ("list all installed packages", "dpkg -l", "packages"),
    ("list installed packages matching a pattern", "dpkg -l | grep {pattern}", "packages"),
    ("show which package owns a specific file", "dpkg -S {file}", "packages"),
    ("list files installed by a package", "dpkg -L {package}", "packages"),
    ("remove unused dependencies that are no longer needed", "apt autoremove -y", "packages"),
    ("clean the local package cache", "apt clean", "packages"),
    ("add a new apt repository", "add-apt-repository {repository}", "packages"),
    ("list configured apt repositories", "cat /etc/apt/sources.list /etc/apt/sources.list.d/*.list", "packages"),

    # ══════════════════════════════════════════════════════════════
    # DOCKER — 20 intents
    # ══════════════════════════════════════════════════════════════
    ("list running docker containers", "docker ps", "docker"),
    ("list all docker containers including stopped ones", "docker ps -a", "docker"),
    ("list docker container IDs only", "docker ps -q", "docker"),
    ("show all docker images downloaded locally", "docker images", "docker"),
    ("pull a docker image from a registry", "docker pull {image}", "docker"),
    ("build a docker image from a Dockerfile in current directory", "docker build -t {tag} .", "docker"),
    ("run a docker container from an image", "docker run -d --name {name} {image}", "docker"),
    ("run a container interactively with a shell", "docker run -it {image} bash", "docker"),
    ("start a stopped docker container", "docker start {container}", "docker"),
    ("stop a running docker container", "docker stop {container}", "docker"),
    ("restart a docker container", "docker restart {container}", "docker"),
    ("remove a docker container", "docker rm {container}", "docker"),
    ("remove a docker image", "docker rmi {image}", "docker"),
    ("remove all stopped containers", "docker container prune -f", "docker"),
    ("show logs from a docker container", "docker logs {container}", "docker"),
    ("follow docker container logs in real time", "docker logs -f {container}", "docker"),
    ("execute a command inside a running docker container", "docker exec -it {container} {command}", "docker"),
    ("open a bash shell inside a running container", "docker exec -it {container} bash", "docker"),
    ("show resource usage of all running containers", "docker stats", "docker"),
    ("show detailed information about a docker container", "docker inspect {container}", "docker"),

    # ══════════════════════════════════════════════════════════════
    # GIT — 5 intents (minimal — already well covered in seeds)
    # ══════════════════════════════════════════════════════════════
    ("show the current state of the git working directory", "git status", "git"),
    ("show commit history in a compact oneline format", "git log --oneline", "git"),
    ("stage all changed files for commit", "git add .", "git"),
    ("commit staged changes with a descriptive message", "git commit -m '{message}'", "git"),
    ("push local commits to the remote origin", "git push", "git"),
]


def normalise(cmd: str) -> str:
    """Strip whitespace so template comparison is robust."""
    return " ".join(cmd.split())


def cmd_family(cmd: str) -> str:
    """Return the first word of a command (the tool name)."""
    return normalise(cmd).split()[0]


def families_match(a: str, b: str) -> bool:
    """True when both commands share the same tool family."""
    return cmd_family(a) == cmd_family(b)


def run_training(db_path: str) -> None:
    kb = KnowledgeBase(db_path)

    before = kb.rule_count
    if before == 0:
        kb.seed_defaults()
        before = kb.rule_count

    print(f"Starting KB training — {before} rules in database")
    print(f"Testing {len(INTENTS)} intents...\n")

    correct = 0
    added = 0
    skipped_family_match = 0
    no_match = 0

    for i, (intent, expected_cmd, category) in enumerate(INTENTS, 1):
        results = kb.search(intent, limit=3)
        exp_norm = normalise(expected_cmd)

        if not results:
            # No results at all — add the rule
            kb.add_rule(intent, expected_cmd, category)
            added += 1
            no_match += 1
            if added <= 10 or added % 50 == 0:
                print(f"  #{i:03d} + [{category:12s}] no match → added: {intent}")
            continue

        best = results[0]
        got_norm = normalise(best["command"])

        if got_norm == exp_norm:
            correct += 1
        elif families_match(expected_cmd, best["command"]):
            # Same tool family, different template — close enough, don't bloat
            correct += 1
            skipped_family_match += 1
        else:
            # Wrong command family — add a corrected rule
            kb.add_rule(intent, expected_cmd, category)
            added += 1
            if added <= 10 or added % 50 == 0:
                print(
                    f"  #{i:03d} ✗ [{category:12s}] mismatch:"
                )
                print(f"         intent:  {intent}")
                print(f"         expected: {exp_norm}")
                print(f"         got:      {got_norm}")

        if i % 50 == 0:
            print(f"  ... {i}/{len(INTENTS)} done ({correct} correct, {added} added)")

    after = kb.rule_count
    print(f"\n{'=' * 65}")
    print(f"Training complete — {len(INTENTS)} intents processed")
    print(f"  Correct:           {correct} ({correct / len(INTENTS) * 100:.1f}%)")
    print(f"  Same family:       {skipped_family_match} (counted as correct)")
    print(f"  No match:          {no_match}")
    print(f"  Rules added:       {added}")
    print(f"  Rules before:      {before}")
    print(f"  Rules after:       {after}")
    print(f"  Δ:                 +{after - before}")
    kb.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the Nulix knowledge base")
    parser.add_argument(
        "--db",
        default="/opt/nulix/knowledge.db",
        help="Path to the SQLite KB (default: /opt/nulix/knowledge.db)",
    )
    args = parser.parse_args()
    run_training(args.db)
