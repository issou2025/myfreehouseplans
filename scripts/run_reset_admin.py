import subprocess, os
repo = os.path.abspath('.')
print('Repo:', repo)
env = os.environ.copy()
env['FLASK_APP'] = 'wsgi:app'
env['ADMIN_PASSWORD'] = 'AdminChangeMe!2026'
print('Running: flask reset-admin-password --username admin')
subprocess.check_call(['flask', 'reset-admin-password', '--username', 'admin'], cwd=repo, env=env)
print('Done')
