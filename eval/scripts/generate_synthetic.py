#!/usr/bin/env python3
"""
generate_synthetic.py — Create synthetic bug cases with 100% ground truth.

Usage:
    python -m eval.scripts.generate_synthetic

Output:
    eval/dataset/synthetic/*.jsonl
"""

import json
from pathlib import Path

OUTPUT_DIR = Path("eval/dataset/synthetic")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Each case: clean code + buggy version + expected finding
SYNTHETIC_CASES = [
    {
        "id": "syn_001_nil_map",
        "description": "Write to nil map causes panic",
        "diff": """\
diff --git a/pkg/cache/cache.go b/pkg/cache/cache.go
+++ b/pkg/cache/cache.go
@@ -0,0 +1,12 @@
+package cache
+
+type Cache struct {
+\tdata map[string]string
+}
+
+func New() *Cache {
+\treturn &Cache{}
+}
+
+func (c *Cache) Set(key, value string) {
+\tc.data[key] = value
+}""",
        "files": ["pkg/cache/cache.go"],
        "expected": {
            "category": "bug",
            "severity": "blocker",
            "message_contains": ["nil map", "panic", "initialize"],
        },
    },
    {
        "id": "syn_002_race_condition",
        "description": "Concurrent map access without mutex",
        "diff": """\
diff --git a/pkg/store/store.go b/pkg/store/store.go
+++ b/pkg/store/store.go
@@ -0,0 +1,20 @@
+package store
+
+import "sync"
+
+type Store struct {
+\tdata map[string]int
+\twg   sync.WaitGroup
+}
+
+func (s *Store) Increment(key string) {
+\ts.wg.Add(1)
+\tgo func() {
+\t\tdefer s.wg.Done()
+\t\ts.data[key]++
+\t}()
+}
+
+func (s *Store) Wait() {
+\ts.wg.Wait()
+}""",
        "files": ["pkg/store/store.go"],
        "expected": {
            "category": "bug",
            "severity": "blocker",
            "message_contains": ["race", "mutex", "concurrent", "sync"],
        },
    },
    {
        "id": "syn_003_missing_error_check",
        "description": "Ignored error return from os.Open",
        "diff": """\
diff --git a/pkg/config/loader.go b/pkg/config/loader.go
+++ b/pkg/config/loader.go
@@ -0,0 +1,15 @@
+package config
+
+import (
+\t"encoding/json"
+\t"os"
+)
+
+func Load(path string) map[string]string {
+\tf, _ := os.Open(path)
+\tdefer f.Close()
+
+\tvar cfg map[string]string
+\tjson.NewDecoder(f).Decode(&cfg)
+\treturn cfg
+}""",
        "files": ["pkg/config/loader.go"],
        "expected": {
            "category": "bug",
            "severity": "major",
            "message_contains": ["error", "ignored", "_"],
        },
    },
    {
        "id": "syn_004_context_leak",
        "description": "Goroutine ignores context cancellation",
        "diff": """\
diff --git a/pkg/worker/worker.go b/pkg/worker/worker.go
+++ b/pkg/worker/worker.go
@@ -0,0 +1,20 @@
+package worker
+
+import (
+\t"context"
+\t"time"
+)
+
+func StartWorker(ctx context.Context, jobs <-chan string) {
+\tgo func() {
+\t\tfor {
+\t\t\tselect {
+\t\t\tcase job := <-jobs:
+\t\t\t\tprocessJob(job)
+\t\t\t}
+\t\t}
+\t}()
+}
+
+func processJob(job string) {
+\ttime.Sleep(100 * time.Millisecond)
+}""",
        "files": ["pkg/worker/worker.go"],
        "expected": {
            "category": "bug",
            "severity": "major",
            "message_contains": ["context", "cancel", "leak", "ctx.Done"],
        },
    },
    {
        "id": "syn_005_integer_overflow",
        "description": "Potential integer overflow in loop counter",
        "diff": """\
diff --git a/pkg/math/sum.go b/pkg/math/sum.go
+++ b/pkg/math/sum.go
@@ -0,0 +1,12 @@
+package math
+
+func SumSlice(nums []int32) int32 {
+\tvar total int32
+\tfor _, n := range nums {
+\t\ttotal += n
+\t}
+\treturn total
+}""",
        "files": ["pkg/math/sum.go"],
        "expected": {
            "category": "bug",
            "severity": "major",
            "message_contains": ["overflow", "int64", "int32"],
        },
    },
    {
        "id": "syn_006_sql_injection",
        "description": "SQL injection via string concatenation",
        "diff": """\
diff --git a/pkg/db/query.go b/pkg/db/query.go
+++ b/pkg/db/query.go
@@ -0,0 +1,15 @@
+package db
+
+import "database/sql"
+
+func GetUser(db *sql.DB, username string) (*sql.Row, error) {
+\tquery := "SELECT * FROM users WHERE username = '" + username + "'"
+\trow := db.QueryRow(query)
+\treturn row, nil
+}""",
        "files": ["pkg/db/query.go"],
        "expected": {
            "category": "security",
            "severity": "blocker",
            "message_contains": ["injection", "parameterized", "prepared"],
        },
    },
    {
        "id": "syn_007_defer_in_loop",
        "description": "Defer inside loop causes resource leak",
        "diff": """\
diff --git a/pkg/files/reader.go b/pkg/files/reader.go
+++ b/pkg/files/reader.go
@@ -0,0 +1,18 @@
+package files
+
+import (
+\t"io"
+\t"os"
+)
+
+func ReadAll(paths []string) [][]byte {
+\tvar results [][]byte
+\tfor _, path := range paths {
+\t\tf, err := os.Open(path)
+\t\tif err != nil {
+\t\t\tcontinue
+\t\t}
+\t\tdefer f.Close()
+\t\tdata, _ := io.ReadAll(f)
+\t\tresults = append(results, data)
+\t}
+\treturn results
+}""",
        "files": ["pkg/files/reader.go"],
        "expected": {
            "category": "bug",
            "severity": "major",
            "message_contains": ["defer", "loop", "leak", "close"],
        },
    },
    {
        "id": "syn_008_weak_crypto",
        "description": "MD5 used for password hashing",
        "diff": """\
diff --git a/pkg/auth/hash.go b/pkg/auth/hash.go
+++ b/pkg/auth/hash.go
@@ -0,0 +1,12 @@
+package auth
+
+import (
+\t"crypto/md5"
+\t"fmt"
+)
+
+func HashPassword(password string) string {
+\th := md5.New()
+\th.Write([]byte(password))
+\treturn fmt.Sprintf("%x", h.Sum(nil))
+}""",
        "files": ["pkg/auth/hash.go"],
        "expected": {
            "category": "security",
            "severity": "blocker",
            "message_contains": ["MD5", "bcrypt", "argon2", "cryptographic"],
        },
    },
    {
        "id": "syn_009_nil_pointer",
        "description": "Nil pointer dereference without check",
        "diff": """\
diff --git a/pkg/user/handler.go b/pkg/user/handler.go
+++ b/pkg/user/handler.go
@@ -0,0 +1,15 @@
+package user
+
+type User struct {
+\tName  string
+\tEmail string
+}
+
+type Service struct {
+\tcurrent *User
+}
+
+func (s *Service) GetName() string {
+\treturn s.current.Name
+}""",
        "files": ["pkg/user/handler.go"],
        "expected": {
            "category": "bug",
            "severity": "blocker",
            "message_contains": ["nil", "pointer", "check"],
        },
    },
    {
        "id": "syn_010_missing_mutex_init",
        "description": "Mutex copied by value",
        "diff": """\
diff --git a/pkg/lock/locker.go b/pkg/lock/locker.go
+++ b/pkg/lock/locker.go
@@ -0,0 +1,20 @@
+package lock
+
+import "sync"
+
+type Locker struct {
+\tmu   sync.Mutex
+\tdata map[string]int
+}
+
+func NewLocker() Locker {
+\treturn Locker{
+\t\tdata: make(map[string]int),
+\t}
+}
+
+func (l Locker) Set(key string, val int) {
+\tl.mu.Lock()
+\tdefer l.mu.Unlock()
+\tl.data[key] = val
+}""",
        "files": ["pkg/lock/locker.go"],
        "expected": {
            "category": "bug",
            "severity": "blocker",
            "message_contains": ["mutex", "copy", "pointer", "value receiver"],
        },
    },
]

# Clean cases — bot should NOT complain
CLEAN_CASES = [
    {
        "id": "clean_001_simple_add",
        "description": "Simple correct addition function",
        "diff": """\
diff --git a/pkg/math/add.go b/pkg/math/add.go
+++ b/pkg/math/add.go
@@ -0,0 +1,8 @@
+package math
+
+// Add returns the sum of two integers.
+func Add(a, b int) int {
+\treturn a + b
+}""",
        "files": ["pkg/math/add.go"],
        "expected_empty": True,
    },
    {
        "id": "clean_002_proper_error_handling",
        "description": "Correct error handling with context",
        "diff": """\
diff --git a/pkg/config/loader.go b/pkg/config/loader.go
+++ b/pkg/config/loader.go
@@ -0,0 +1,20 @@
+package config
+
+import (
+\t"encoding/json"
+\t"fmt"
+\t"os"
+)
+
+func Load(path string) (map[string]string, error) {
+\tf, err := os.Open(path)
+\tif err != nil {
+\t\treturn nil, fmt.Errorf("open config: %w", err)
+\t}
+\tdefer f.Close()
+
+\tvar cfg map[string]string
+\tif err := json.NewDecoder(f).Decode(&cfg); err != nil {
+\t\treturn nil, fmt.Errorf("decode config: %w", err)
+\t}
+\treturn cfg, nil
+}""",
        "files": ["pkg/config/loader.go"],
        "expected_empty": True,
    },
    {
        "id": "clean_003_proper_mutex",
        "description": "Correct mutex usage with pointer receiver",
        "diff": """\
diff --git a/pkg/store/store.go b/pkg/store/store.go
+++ b/pkg/store/store.go
@@ -0,0 +1,25 @@
+package store
+
+import "sync"
+
+type Store struct {
+\tmu   sync.RWMutex
+\tdata map[string]int
+}
+
+func New() *Store {
+\treturn &Store{data: make(map[string]int)}
+}
+
+func (s *Store) Set(key string, val int) {
+\ts.mu.Lock()
+\tdefer s.mu.Unlock()
+\ts.data[key] = val
+}
+
+func (s *Store) Get(key string) (int, bool) {
+\ts.mu.RLock()
+\tdefer s.mu.RUnlock()
+\tv, ok := s.data[key]
+\treturn v, ok
+}""",
        "files": ["pkg/store/store.go"],
        "expected_empty": True,
    },
]


def main():
    # Save synthetic bugs
    bug_file = OUTPUT_DIR / "bugs.jsonl"
    with open(bug_file, "w") as f:
        for case in SYNTHETIC_CASES:
            case["source"] = "synthetic"
            case["human_labels"] = [{
                "comment_id": f"synthetic_{case['id']}",
                "file": case["files"][0],
                "line": 1,
                "body": f"Expected: {case['description']}",
                "type": case["expected"]["category"],
                "severity": case["expected"]["severity"],
                "catchable_by_llm": True,
                "already_caught_by_linter": False,
            }]
            f.write(json.dumps(case) + "\n")

    print(f"✅ {len(SYNTHETIC_CASES)} synthetic bug cases → {bug_file}")

    # Save clean cases
    clean_dir = Path("eval/dataset/clean")
    clean_dir.mkdir(parents=True, exist_ok=True)
    clean_file = clean_dir / "clean_cases.jsonl"
    with open(clean_file, "w") as f:
        for case in CLEAN_CASES:
            case["source"] = "clean"
            case["human_labels"] = []
            f.write(json.dumps(case) + "\n")

    print(f"✅ {len(CLEAN_CASES)} clean cases → {clean_file}")
    print(f"\nTotal synthetic: {len(SYNTHETIC_CASES)} bug + {len(CLEAN_CASES)} clean = {len(SYNTHETIC_CASES) + len(CLEAN_CASES)} cases")


if __name__ == "__main__":
    main()
