# Admin Password Reset Guide

## Problem
If you can't log in to the admin dashboard with the expected credentials, the admin password may not match the environment variable.

## Production Credentials
- **Username**: from `ADMIN_USERNAME`
- **Email**: from `ADMIN_EMAIL`
- **Password**: from `ADMIN_PASSWORD` (managed in Render dashboard)

## Automatic Reset on Deploy
The admin password is automatically reset during deployment thanks to the `releaseCommand` in `render.yaml`:

```yaml
releaseCommand: flask db upgrade && flask reset-admin-password
```

This command:
1. Runs database migrations
2. Resets the admin password from the `ADMIN_PASSWORD` environment variable
3. Ensures admin has proper permissions

## Manual Password Reset

### On Render (Production)
If the automatic reset doesn't work, you can manually run the command via Render Shell:

1. Go to your Render dashboard
2. Select your service
3. Click "Shell" tab
4. Run: `flask reset-admin-password`

The command will use the `ADMIN_PASSWORD` environment variable set in Render.

### Locally (Development)
To reset the local admin password:

```bash
# Using environment variable
export ADMIN_PASSWORD="your_new_password"
flask reset-admin-password

# Or interactive prompt
flask reset-admin-password
```

## Creating New Admin User
To create a completely new admin user:

```bash
flask create-admin --username newadmin --email admin@example.com
# You'll be prompted for password
```

## Environment Variables
The following environment variables are used:
- `ADMIN_USERNAME` (default: admin)
- `ADMIN_EMAIL` (default: admin@myfreehouseplans.com)  
- `ADMIN_PASSWORD` (no default in production; must be set in Render)

## Verification
After resetting, the command will show:
```
✓ Password updated for user 'admin' (admin@myfreehouseplans.com)
✓ Admin status: True
✓ Active status: True
```

## Next Deployment
Every time you deploy to Render:
1. The `releaseCommand` runs automatically
2. Admin password syncs with `ADMIN_PASSWORD` environment variable
3. You can log in immediately with the production credentials

## Security Notes
- Never commit passwords to git
- Use strong passwords in production
- Consider using Render's secret management for sensitive values
- Change the default password immediately after first login
