import subprocess, os
repo = os.path.abspath('.')
print('Repo:', repo)
env = os.environ.copy()
env['FLASK_APP'] = 'wsgi:app'
admin_password = env.get('ADMIN_PASSWORD')
if not admin_password:
	raise SystemExit('ADMIN_PASSWORD is required (refusing to use a hardcoded value)')

admin_username = env.get('ADMIN_USERNAME', 'admin')
print(f'Running: flask reset-admin-password --username {admin_username}')
subprocess.check_call(['flask', 'reset-admin-password', '--username', admin_username], cwd=repo, env=env)
print('Done')
