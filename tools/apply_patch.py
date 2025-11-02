#!/usr/bin/env python3
import sys, subprocess, tempfile, os

patch = sys.stdin.read().strip()
if not patch:
    print("No patch on stdin.", file=sys.stderr)
    sys.exit(1)

with tempfile.NamedTemporaryFile('w', delete=False, suffix=".patch") as f:
    f.write(patch)
    path = f.name

# Test if patch applies
chk = subprocess.run(["git", "apply", "--check", path], capture_output=True, text=True)
if chk.returncode != 0:
    print("❌ Patch does not apply cleanly:\n", chk.stderr, file=sys.stderr)
    os.unlink(path)
    sys.exit(chk.returncode)

# Determine base branch
try:
    subprocess.run(["git", "rev-parse", "--verify", "HEAD"], stdout=subprocess.DEVNULL)
    base_branch = "main"
except:
    base_branch = None

branch = os.environ.get("PATCH_BRANCH", f"ai/patch-{os.path.basename(path)}")

if base_branch:
    subprocess.run(["git", "checkout", base_branch], check=False)
    subprocess.run(["git", "pull"], check=False)

subprocess.run(["git", "checkout", "-b", branch], check=False)
subprocess.check_call(["git", "apply", "--index", path])
subprocess.check_call(["git", "commit", "-m", "chore(ai): apply patch"])
print(f"✅ Patch applied on branch: {branch}")

os.unlink(path)
