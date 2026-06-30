from __future__ import annotations

import sqlite3
import re
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# FTS5 query helpers
# ---------------------------------------------------------------------------

_FTS_SPECIAL = re.compile(r'[^\w\s*"\-\(\)]')

# Words that add no signal for Linux command search — stripped before FTS5.
_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "all", "both", "each",
    "every", "few", "more", "most", "other", "some", "such", "only",
    "own", "same", "so", "than", "too", "very", "just", "now", "out",
    "up", "down", "off", "over", "about", "how", "what", "which", "who",
    "whom", "this", "that", "these", "those", "me", "him", "her", "my",
    "your", "its", "our", "their", "i", "you", "he", "she", "it", "we",
    "they", "let", "need", "want", "like", "get", "got", "make", "made",
    "go", "going", "please", "tell", "give", "show", "display", "print",
}


def _tokenise(query: str) -> list[str]:
    """Return meaningful lowercased tokens, stop-words removed."""
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _build_fts_query(user_text: str) -> str:
    """Build an FTS5 prefix-match query from user text.

    Appends ``*`` to each token so ``bigger`` matches tokens starting with
    ``bigger`` (unlikely to help on its own, but effective when combined with
    the enriched intent descriptions that include synonyms).
    """
    tokens = _tokenise(user_text)
    if not tokens:
        return "unknown"
    # Join with OR — any token match contributes to the rank
    return " OR ".join(f"{t}*" for t in tokens)


def _sanitise_fts_query(user_text: str) -> str:
    """Remove characters that break FTS5 MATCH syntax (legacy fallback)."""
    cleaned = _FTS_SPECIAL.sub(" ", user_text)
    cleaned = " ".join(cleaned.split())
    return cleaned or "unknown"


# ---------------------------------------------------------------------------
# Seed data — curated intent → command templates
# ---------------------------------------------------------------------------

# Each logical rule may appear multiple times with different intent
# phrasings so that colloquial user queries can match.  The command
# template is identical across duplicates — only the intent text varies.
SEED_RULES: list[tuple[str, str, str]] = [
    # ── files ──────────────────────────────────────────────────────────
    ("list files in a directory", "ls {directory}", "files"),
    ("show contents of a directory", "ls {directory}", "files"),
    ("show contents of a folder", "ls {directory}", "files"),
    ("what is in this folder", "ls {directory}", "files"),
    ("what is inside this directory", "ls {directory}", "files"),
    ("see what files are in a folder", "ls {directory}", "files"),
    ("look inside a folder", "ls {directory}", "files"),
    ("list all files including hidden files", "ls -la {directory}", "files"),
    ("show hidden files too", "ls -la {directory}", "files"),
    ("list everything including dotfiles", "ls -la {directory}", "files"),
    ("list files sorted by size largest first", "ls -lS {directory}", "files"),
    ("sort files by size descending", "ls -lS {directory}", "files"),
    ("biggest files first", "ls -lS {directory}", "files"),
    ("list files sorted by modification time newest first", "ls -lt {directory}", "files"),
    ("sort files by date modified", "ls -lt {directory}", "files"),
    ("most recently changed files first", "ls -lt {directory}", "files"),
    ("find files larger than a given size", 'find {directory} -type f -size +{size}', "files"),
    ("find big files", 'find {directory} -type f -size +{size}', "files"),
    ("search for files bigger than", 'find {directory} -type f -size +{size}', "files"),
    ("files larger than size megabytes", 'find {directory} -type f -size +{size}', "files"),
    ("find files smaller than a given size", 'find {directory} -type f -size -{size}', "files"),
    ("find files by name pattern", "find {directory} -name '{pattern}'", "files"),
    ("search for a file by name", "find {directory} -name '{pattern}'", "files"),
    ("locate a file called something", "find {directory} -name '{pattern}'", "files"),
    ("find directories by name", "find {directory} -type d -name '{pattern}'", "files"),
    ("find files modified in the last N days", "find {directory} -type f -mtime -{days}", "files"),
    ("recently modified files", "find {directory} -type f -mtime -{days}", "files"),
    ("files changed within the past week", "find {directory} -type f -mtime -{days}", "files"),
    ("find empty files", "find {directory} -type f -empty", "files"),
    ("find empty directories", "find {directory} -type d -empty", "files"),
    ("count files in a directory recursively", "find {directory} -type f | wc -l", "files"),
    ("how many files are in this directory", "find {directory} -type f | wc -l", "files"),
    ("count number of files", "find {directory} -type f | wc -l", "files"),
    ("copy a file or directory", "cp -r {source} {destination}", "files"),
    ("duplicate a file", "cp {source} {destination}", "files"),
    ("move or rename a file or directory", "mv {source} {destination}", "files"),
    ("rename a file", "mv {source} {destination}", "files"),
    ("delete a file", "rm {file}", "files"),
    ("remove a file", "rm {file}", "files"),
    ("delete a directory and all its contents", "rm -rf {directory}", "files"),
    ("remove a directory recursively", "rm -rf {directory}", "files"),
    ("nuke a folder", "rm -rf {directory}", "files"),
    ("create a new directory", "mkdir {directory}", "files"),
    ("make a directory", "mkdir {directory}", "files"),
    ("list folder", "ls {directory}", "files"),
    ("folder contents", "ls {directory}", "files"),
    ("create a folder", "mkdir {directory}", "files"),
    ("create nested directories creating parents", "mkdir -p {path}", "files"),
    ("make parent directories as needed", "mkdir -p {path}", "files"),
    ("change file permissions with octal mode", "chmod {mode} {file}", "files"),
    ("set file permissions", "chmod {mode} {file}", "files"),
    ("make a file executable", "chmod +x {file}", "files"),
    ("add execute permission to a file", "chmod +x {file}", "files"),
    ("change file owner and group", "chown {user}:{group} {file}", "files"),
    ("find files by extension", "find {directory} -name '*.{ext}'", "files"),
    ("find all python files", "find {directory} -name '*.{ext}'", "files"),
    ("find all log files", "find {directory} -name '*.{ext}'", "files"),
    ("find all txt text files", "find {directory} -name '*.{ext}'", "files"),
    ("find files ending with a suffix", "find {directory} -name '*.{ext}'", "files"),
    ("show disk usage of a directory summarised", "du -sh {directory}", "files"),
    ("how big is this directory", "du -sh {directory}", "files"),
    ("folder size", "du -sh {directory}", "files"),
    ("show free and used disk space on all filesystems", "df -h", "files"),
    ("disk space free", "df -h", "files"),
    ("how much space is left on disk", "df -h", "files"),
    ("check available disk space", "df -h", "files"),
    ("create a symbolic link", "ln -s {target} {link_name}", "files"),
    ("make a symlink", "ln -s {target} {link_name}", "files"),
    ("find and delete files matching a pattern", "find {directory} -name '{pattern}' -delete", "files"),
    ("show what type a file is", "file {path}", "files"),
    ("identify file type", "file {path}", "files"),
    ("create a tar gzip archive", "tar -czf {archive}.tar.gz {directory}", "files"),
    ("compress directory to tar gz", "tar -czf {archive}.tar.gz {directory}", "files"),
    ("tar and gzip a folder", "tar -czf {archive}.tar.gz {directory}", "files"),
    ("extract a tar gzip archive", "tar -xzf {archive}.tar.gz", "files"),
    ("uncompress tar gz file", "tar -xzf {archive}.tar.gz", "files"),
    ("create a zip archive", "zip -r {archive}.zip {directory}", "files"),
    ("zip a directory", "zip -r {archive}.zip {directory}", "files"),
    ("extract a zip archive", "unzip {archive}.zip", "files"),
    ("unzip a file", "unzip {archive}.zip", "files"),
    ("show file or directory size", "du -sh {path}", "files"),
    ("size of a file", "du -sh {path}", "files"),
    ("compare two files line by line", "diff {file1} {file2}", "files"),
    ("diff two files", "diff {file1} {file2}", "files"),

    # ── text ───────────────────────────────────────────────────────────
    ("search for text recursively in files", "grep -r '{pattern}' {directory}", "text"),
    ("look for string in files", "grep -r '{pattern}' {directory}", "text"),
    ("find text inside files", "grep -r '{pattern}' {directory}", "text"),
    ("search for something in all files", "grep -r '{pattern}' {directory}", "text"),
    ("grep for text in specific file types by extension", "grep -r '{pattern}' {directory} --include='*.{ext}'", "text"),
    ("search for string in python files", "grep -r '{pattern}' {directory} --include='*.{ext}'", "text"),
    ("find text in all files of a certain type", "grep -r '{pattern}' {directory} --include='*.{ext}'", "text"),
    ("search for text case insensitive recursively", "grep -ri '{pattern}' {directory}", "text"),
    ("count lines in a file", "wc -l {file}", "text"),
    ("how many lines in a file", "wc -l {file}", "text"),
    ("line count", "wc -l {file}", "text"),
    ("count words in a file", "wc -w {file}", "text"),
    ("show the first N lines of a file", "head -n {count} {file}", "text"),
    ("top lines of a file", "head -n {count} {file}", "text"),
    ("show the last N lines of a file", "tail -n {count} {file}", "text"),
    ("bottom of a file", "tail -n {count} {file}", "text"),
    ("end of log file", "tail -n {count} {file}", "text"),
    ("follow a log file showing new lines as they are written", "tail -f {file}", "text"),
    ("watch a log file live", "tail -f {file}", "text"),
    ("stream log output", "tail -f {file}", "text"),
    ("sort lines of a file alphabetically", "sort {file}", "text"),
    ("sort lines numerically", "sort -n {file}", "text"),
    ("sort and remove duplicate lines", "sort -u {file}", "text"),
    ("deduplicate lines in file", "sort -u {file}", "text"),
    ("count occurrences of unique lines sorted by frequency", "sort {file} | uniq -c | sort -rn", "text"),
    ("most frequent lines in a file", "sort {file} | uniq -c | sort -rn", "text"),
    ("replace text in a file in place using sed", "sed -i 's/{old}/{new}/g' {file}", "text"),
    ("find and replace in a file", "sed -i 's/{old}/{new}/g' {file}", "text"),
    ("substitute string in file", "sed -i 's/{old}/{new}/g' {file}", "text"),
    ("find and replace text across multiple files by extension", "find {dir} -name '*.{ext}' -exec sed -i 's/{old}/{new}/g' {} +", "text"),
    ("show lines matching a pattern in a file", "grep '{pattern}' {file}", "text"),
    ("filter lines containing string", "grep '{pattern}' {file}", "text"),

    # ── processes ──────────────────────────────────────────────────────
    ("list all running processes", "ps aux", "processes"),
    ("show processes", "ps aux", "processes"),
    ("what is running on this machine", "ps aux", "processes"),
    ("list processes sorted by CPU usage", "ps aux --sort=-%cpu", "processes"),
    ("what is using the most cpu", "ps aux --sort=-%cpu", "processes"),
    ("list processes sorted by memory usage", "ps aux --sort=-%mem", "processes"),
    ("what is using the most ram", "ps aux --sort=-%mem", "processes"),
    ("what process is consuming the most memory", "ps aux --sort=-%mem", "processes"),
    ("find process using most resources", "ps aux --sort=-%mem", "processes"),
    ("which program is using the most memory", "ps aux --sort=-%mem", "processes"),
    ("show processes sorted by how much memory they use", "ps aux --sort=-%mem", "processes"),
    ("find a process by name or keyword", "ps aux | grep {name}", "processes"),
    ("is a process running", "ps aux | grep {name}", "processes"),
    ("search for a running program", "ps aux | grep {name}", "processes"),
    ("kill a process by its PID number", "kill {pid}", "processes"),
    ("terminate a process by pid", "kill {pid}", "processes"),
    ("force kill a process by its PID number", "kill -9 {pid}", "processes"),
    ("forcefully terminate a process by pid", "kill -9 {pid}", "processes"),
    ("kill all processes by name", "pkill {name}", "processes"),
    ("kill process by name", "pkill {name}", "processes"),
    ("kill by program name", "pkill {name}", "processes"),
    ("kill a process when you know its name", "pkill {name}", "processes"),
    ("stop a program by name", "pkill {name}", "processes"),
    ("terminate a program by its name", "pkill {name}", "processes"),
    ("kill firefox or any named application", "pkill {name}", "processes"),
    ("show a tree of running processes", "pstree", "processes"),
    ("process hierarchy", "pstree", "processes"),
    ("show the process ID of a running program", "pgrep {name}", "processes"),
    ("find pid of a program", "pgrep {name}", "processes"),

    # ── networking ─────────────────────────────────────────────────────
    ("show listening TCP ports", "ss -tlnp", "networking"),
    ("what ports are listening", "ss -tlnp", "networking"),
    ("list open ports", "ss -tlnp", "networking"),
    ("show all network connections", "ss -tunap", "networking"),
    ("active network connections", "ss -tunap", "networking"),
    ("show network interfaces and their IP addresses", "ip addr show", "networking"),
    ("what is my local ip address", "ip addr show", "networking"),
    ("show the public IP address of this machine", "curl -s ifconfig.me", "networking"),
    ("what is my public ip", "curl -s ifconfig.me", "networking"),
    ("check whether a remote host is reachable", "ping -c {count} {host}", "networking"),
    ("ping a server", "ping -c {count} {host}", "networking"),
    ("is hostname reachable", "ping -c {count} {host}", "networking"),
    ("download a file with curl saving with remote name", "curl -O {url}", "networking"),
    ("download a file", "curl -O {url}", "networking"),
    ("download a file with wget", "wget {url}", "networking"),
    ("query DNS records for a domain", "dig {domain}", "networking"),
    ("lookup dns", "dig {domain}", "networking"),
    ("test if a TCP port is open on a remote host", "nc -zv {host} {port}", "networking"),
    ("check if port is open", "nc -zv {host} {port}", "networking"),
    ("trace the network path to a remote host", "traceroute {host}", "networking"),
    ("resolve a hostname to an IP address", "dig +short {hostname}", "networking"),

    # ── system ─────────────────────────────────────────────────────────
    ("show memory usage in human readable form", "free -h", "system"),
    ("how much memory is free", "free -h", "system"),
    ("ram usage", "free -h", "system"),
    ("available memory", "free -h", "system"),
    ("show how long the system has been running", "uptime", "system"),
    ("system uptime", "uptime", "system"),
    ("how long has this server been up", "uptime", "system"),
    ("show the kernel version", "uname -r", "system"),
    ("kernel version", "uname -r", "system"),
    ("show operating system release information", "cat /etc/os-release", "system"),
    ("what os is this", "cat /etc/os-release", "system"),
    ("show the status of a systemd service", "systemctl status {service}", "system"),
    ("status of a service", "systemctl status {service}", "system"),
    ("is a service running", "systemctl status {service}", "system"),
    ("check if a service is active", "systemctl status {service}", "system"),
    ("start a systemd service", "systemctl start {service}", "system"),
    ("start a service", "systemctl start {service}", "system"),
    ("stop a systemd service", "systemctl stop {service}", "system"),
    ("stop a service", "systemctl stop {service}", "system"),
    ("restart a systemd service", "systemctl restart {service}", "system"),
    ("restart a service", "systemctl restart {service}", "system"),
    ("enable a systemd service to start at boot", "systemctl enable {service}", "system"),
    ("disable a systemd service from starting at boot", "systemctl disable {service}", "system"),
    ("follow journal logs for a specific service", "journalctl -u {service} -f", "system"),
    ("show logs for a service", "journalctl -u {service} -f", "system"),
    ("show the most recent journal log entries", "journalctl -n {count}", "system"),
    ("recent system logs", "journalctl -n {count}", "system"),
    ("show CPU information", "lscpu", "system"),
    ("cpu details", "lscpu", "system"),
    ("show block device information", "lsblk", "system"),
    ("list disks and partitions", "lsblk", "system"),
    ("show the current date and time", "date", "system"),
    ("what time is it", "date", "system"),
    ("show system hostname", "hostname", "system"),
    ("what is the hostname of this machine", "hostname", "system"),

    # ── users / permissions ────────────────────────────────────────────
    ("show the current user name", "whoami", "users"),
    ("who am i logged in as", "whoami", "users"),
    ("current logged in user", "whoami", "users"),
    ("show who is currently logged in", "who", "users"),
    ("who is on this system", "who", "users"),
    ("show user and group information", "id {username}", "users"),
    ("show what groups a user belongs to", "groups {username}", "users"),
    ("list all local user accounts", "cat /etc/passwd | cut -d: -f1", "users"),
    ("add a new user with home directory", "useradd -m {username}", "users"),
    ("create a user account", "useradd -m {username}", "users"),
    ("change a user password", "passwd {username}", "users"),
    ("set password for user", "passwd {username}", "users"),
    ("switch to another user", "su - {username}", "users"),
    ("become another user", "su - {username}", "users"),
    ("run a command as another user with sudo", "sudo -u {username} {command}", "users"),

    # ── package management (apt / debian) ──────────────────────────────
    ("install a package with apt", "apt install -y {package}", "packages"),
    ("install a program", "apt install -y {package}", "packages"),
    ("apt get install something", "apt install -y {package}", "packages"),
    ("remove a package with apt", "apt remove -y {package}", "packages"),
    ("uninstall a package", "apt remove -y {package}", "packages"),
    ("update the package list", "apt update", "packages"),
    ("refresh apt cache", "apt update", "packages"),
    ("upgrade all installed packages", "apt upgrade -y", "packages"),
    ("update all packages", "apt upgrade -y", "packages"),
    ("search for a package by name", "apt search {package}", "packages"),
    ("find a package in apt", "apt search {package}", "packages"),
    ("list all installed packages", "dpkg -l", "packages"),

    # ── docker ─────────────────────────────────────────────────────────
    ("list running docker containers", "docker ps", "docker"),
    ("show docker containers running", "docker ps", "docker"),
    ("list all docker containers including stopped", "docker ps -a", "docker"),
    ("show all docker containers", "docker ps -a", "docker"),
    ("list docker images", "docker images", "docker"),
    ("show docker images", "docker images", "docker"),
    ("start a docker container", "docker start {container}", "docker"),
    ("stop a docker container", "docker stop {container}", "docker"),
    ("remove a docker container", "docker rm {container}", "docker"),
    ("delete docker container", "docker rm {container}", "docker"),
    ("show logs of a docker container", "docker logs {container}", "docker"),
    ("docker container logs", "docker logs {container}", "docker"),
    ("follow logs of a docker container", "docker logs -f {container}", "docker"),
    ("run a command inside a running docker container", "docker exec -it {container} {command}", "docker"),
    ("exec into docker container", "docker exec -it {container} {command}", "docker"),
    ("shell into a docker container", "docker exec -it {container} bash", "docker"),

    # ── git ────────────────────────────────────────────────────────────
    ("show the git status of the working tree", "git status", "git"),
    ("git status", "git status", "git"),
    ("what changed in git", "git status", "git"),
    ("show git commit history", "git log --oneline", "git"),
    ("git log", "git log --oneline", "git"),
    ("show recent commits", "git log --oneline", "git"),
    ("stage all changes for commit", "git add .", "git"),
    ("git add all files", "git add .", "git"),
    ("stage everything", "git add .", "git"),
    ("commit staged changes with a message", "git commit -m '{message}'", "git"),
    ("git commit", "git commit -m '{message}'", "git"),
    ("push commits to the remote repository", "git push", "git"),
    ("git push", "git push", "git"),
    ("pull latest changes from the remote repository", "git pull", "git"),
    ("git pull", "git pull", "git"),
    ("create a new git branch", "git checkout -b {branch}", "git"),
    ("new branch", "git checkout -b {branch}", "git"),
    ("switch to an existing git branch", "git checkout {branch}", "git"),
    ("change branch", "git checkout {branch}", "git"),
    ("list all git branches", "git branch -a", "git"),
    ("show branches", "git branch -a", "git"),
    ("show changes between working tree and last commit", "git diff", "git"),
    ("git diff", "git diff", "git"),
    ("what did i change", "git diff", "git"),
    ("clone a git repository", "git clone {url}", "git"),
    ("git clone", "git clone {url}", "git"),
]


# ---------------------------------------------------------------------------
# KnowledgeBase
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """SQLite + FTS5 knowledge base storing intent → command mappings."""

    def __init__(self, db_path: str = "/opt/nulix/knowledge.db"):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    # ── connection management ──────────────────────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── schema ─────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intent TEXT NOT NULL,
                command TEXT NOT NULL,
                category TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS rules_fts USING fts5(
                intent,
                command,
                category,
                content='rules',
                content_rowid='id'
            );

            -- Triggers to keep the FTS index in sync
            CREATE TRIGGER IF NOT EXISTS rules_ai AFTER INSERT ON rules BEGIN
                INSERT INTO rules_fts(rowid, intent, command, category)
                VALUES (new.id, new.intent, new.command, new.category);
            END;

            CREATE TRIGGER IF NOT EXISTS rules_ad AFTER DELETE ON rules BEGIN
                INSERT INTO rules_fts(rules_fts, rowid, intent, command, category)
                VALUES ('delete', old.id, old.intent, old.command, old.category);
            END;

            CREATE TRIGGER IF NOT EXISTS rules_au AFTER UPDATE ON rules BEGIN
                INSERT INTO rules_fts(rules_fts, rowid, intent, command, category)
                VALUES ('delete', old.id, old.intent, old.command, old.category);
                INSERT INTO rules_fts(rowid, intent, command, category)
                VALUES (new.id, new.intent, new.command, new.category);
            END;
            """
        )
        self.conn.commit()

    # ── search ─────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 3) -> list[dict]:
        """Search rules with FTS5 prefix matching + LIKE fallback.

        Returns a list of dicts with keys: id, intent, command, category, rank.
        Always tries LIKE when FTS5 returns fewer than *limit* results so
        colloquial phrasing (which may share no tokens with the curated
        intents) can still find a match.
        """
        fts_query = _build_fts_query(query)
        results: list[dict] = []

        # ── FTS5 prefix-match pass ────────────────────────────────
        try:
            rows = self.conn.execute(
                """
                SELECT r.id, r.intent, r.command, r.category, f.rank
                FROM rules_fts f
                JOIN rules r ON r.id = f.rowid
                WHERE rules_fts MATCH ?
                ORDER BY f.rank
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
            results = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            pass  # fall through to LIKE

        # ── LIKE fallback — fill remaining slots ──────────────────
        if len(results) < limit:
            seen = {r["id"] for r in results}
            needed = limit - len(results)
            tokens = _tokenise(query)
            if tokens:
                # Build a LIKE clause that prefers intent matches
                like_clauses = " OR ".join(["intent LIKE ?"] * len(tokens) + ["command LIKE ?"] * len(tokens))
                like_params = [f"%{t}%" for t in tokens] + [f"%{t}%" for t in tokens]
                try:
                    rows = self.conn.execute(
                        f"""
                        SELECT id, intent, command, category, 1.0 AS rank
                        FROM rules
                        WHERE ({like_clauses})
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (*like_params, needed),
                    ).fetchall()
                    for r in rows:
                        d = dict(r)
                        if d["id"] not in seen:
                            results.append(d)
                            seen.add(d["id"])
                except sqlite3.OperationalError:
                    pass

        return results[:limit]

    # ── CRUD ───────────────────────────────────────────────────────

    def add_rule(self, intent: str, command: str, category: str | None = None) -> int:
        """Insert a rule and return its id."""
        cur = self.conn.execute(
            "INSERT INTO rules (intent, command, category) VALUES (?, ?, ?)",
            (intent, command, category),
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_rule(self, rule_id: int) -> bool:
        """Delete a rule by id.  Returns True if a row was removed."""
        cur = self.conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def list_rules(self, category: str | None = None) -> list[dict]:
        """List all rules, optionally filtered by category."""
        if category:
            rows = self.conn.execute(
                "SELECT id, intent, command, category, created_at FROM rules WHERE category = ? ORDER BY id",
                (category,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT id, intent, command, category, created_at FROM rules ORDER BY category, id"
            ).fetchall()
        return [dict(r) for r in rows]

    @property
    def rule_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]

    # ── seed ───────────────────────────────────────────────────────

    def seed_defaults(self) -> int:
        """Populate the database with curated default rules.

        Safe to call repeatedly — skips rules whose (intent, command) pair
        already exists.  Returns the number of newly inserted rows.
        """
        inserted = 0
        for intent, command, category in SEED_RULES:
            cur = self.conn.execute(
                "SELECT COUNT(*) FROM rules WHERE intent = ? AND command = ?",
                (intent, command),
            )
            if cur.fetchone()[0] == 0:
                cur = self.conn.execute(
                    "INSERT INTO rules (intent, command, category) VALUES (?, ?, ?)",
                    (intent, command, category),
                )
                inserted += 1
        if inserted:
            self.conn.commit()
        return inserted


# ---------------------------------------------------------------------------
# Convenience — build a KB from the env var
# ---------------------------------------------------------------------------

def get_knowledge_base() -> KnowledgeBase:
    import os

    path = os.getenv("NULIX_KB_PATH", "/opt/nulix/knowledge.db")
    enabled = os.getenv("NULIX_KB_ENABLED", "true").lower() not in ("0", "false", "no")
    if not enabled:
        return None  # type: ignore[return-value]

    kb = KnowledgeBase(path)
    if kb.rule_count == 0:
        kb.seed_defaults()
    return kb
