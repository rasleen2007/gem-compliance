import os, re
root = r"D:\sih\frontend\src"
rel_re = re.compile(r"from\s+['\"](\.\.?/[^'\"]+)['\"]")
missing, resolved, seen = [], 0, 0
for dp, _, fs in os.walk(root):
    for fn in fs:
        if not fn.endswith((".js", ".jsx")):
            continue
        p = os.path.join(dp, fn)
        try: s = open(p, encoding="utf-8").read()
        except OSError: continue
        seen += 1
        for m in rel_re.finditer(s):
            spec = m.group(1)
            base = os.path.normpath(os.path.join(dp, spec))
            cands = [base]
            if not base.endswith((".js", ".jsx")):
                cands += [base + ".js", base + ".jsx"]
            if any(os.path.isfile(c) for c in cands):
                resolved += 1
            else:
                missing.append((os.path.relpath(p, root), spec))
print("files scanned:", seen)
print("relative imports resolved:", resolved)
print("missing:", len(missing))
for rel, spec in missing:
    print(f"  {rel} -> {spec}")
