import subprocess, sys
import os
repo = os.path.abspath(os.getcwd())
print('Repo:', repo)
try:
    subprocess.check_call(['git', 'add', '-A'], cwd=repo)
    # Commit only if there are staged changes
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).decode().strip()
    if status:
        subprocess.check_call(['git', 'commit', '-m', 'Fix admin authentication and guarantee production login'], cwd=repo)
        print('Committed changes')
    else:
        print('No changes to commit')
    subprocess.check_call(['git', 'push', 'origin', 'main'], cwd=repo)
    print('Pushed to origin/main')
    print('Branch:', subprocess.check_output(['git', 'branch', '--show-current'], cwd=repo).decode().strip())
    print('HEAD:', subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo).decode().strip())
    print('Last 3 commits:')
    print(subprocess.check_output(['git', 'log', '-n', '3', '--pretty=oneline'], cwd=repo).decode())
except subprocess.CalledProcessError as e:
    print('Git command failed:', e)
    sys.exit(1)
