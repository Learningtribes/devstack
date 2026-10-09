import subprocess, sys, re
P, M, MP, MB = sys.argv[1:5]
def git(*a): return subprocess.run(['git']+list(a), capture_output=True, text=True, errors='replace').stdout
files = [f for f in git('diff','--name-only','--diff-filter=AM',MB,P).split('\n') if f.endswith('.py') and not f.startswith(('docs/','.claude/'))]
def blob(rev, f):
    r = subprocess.run(['git','show',f'{rev}:{f}'],capture_output=True,text=True,errors='replace')
    return r.stdout if r.returncode == 0 else None
rows = []
for f in files:
    d = git('diff','-U0',MB,P,'--',f)
    added = [l[1:] for l in d.split('\n') if l.startswith('+') and not l.startswith('+++')]
    removed = [l[1:] for l in d.split('\n') if l.startswith('-') and not l.startswith('---')]
    after = blob(M, f); mside = blob(MP, f); mbase = blob(MB, f)
    if after is None:
        rows.append((f, 'FILE_GONE_AFTER_MERGE', 'master deleted' if mside is None else 'merge deleted', len(added))); continue
    al = set(after.split('\n')); ml = set((mside or '').split('\n'))
    lost = [l for l in added if l.strip() and l not in al]
    back = [l for l in removed if l.strip() and l in al and l not in set((blob(P,f) or '').split('\n'))]
    if lost or back:
        rows.append((f, 'LOST_ADD' if lost else 'REINTRODUCED', '', len(lost)+len(back), lost[:4], back[:4], mside is None))
for r in rows:
    if r[1] == 'FILE_GONE_AFTER_MERGE':
        print(f"{r[1]:22} {r[0]}  ({r[2]}, {r[3]} R1-added lines)")
    else:
        print(f"{'LOST/REINTRODUCED':22} {r[0]}  lost={len(r[4])}+ back={len(r[5])}+")
        for l in r[4]: print('    - lost   :', l.strip()[:110])
        for l in r[5]: print('    + back   :', l.strip()[:110])
print('scanned R1-modified .py files:', len(files), 'flagged:', len(rows))
