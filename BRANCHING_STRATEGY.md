# Branching Strategy & Deployment Flow

## Overview

This repository follows a staged deployment approach with the following branches:

- **feature branches**: For new features and bug fixes (`feature/name-of-feature`)
- **development**: Integration branch for development (optional)
- **staging**: Pre-production testing branch
- **main**: Production branch

## Branch Protection Rules

1. **Direct Pushes to Main Are Not Allowed**
   - All changes to the main branch must go through the staging branch first
   - This ensures proper testing in staging before production deployment

2. **Promotion Process**
   - Code flows from feature branches → staging → main
   - Changes to main are only made by merging from staging

## How to Work with This Repository

### Feature Development

1. Create a feature branch from staging:
   ```bash
   git checkout staging
   git pull origin staging
   git checkout -b feature/your-feature-name
   ```

2. Make your changes, commit, and push to your feature branch:
   ```bash
   git add .
   git commit -m "Description of your changes"
   git push origin feature/your-feature-name
   ```

3. Create a pull request to the **staging** branch (not main)

### Testing in Staging

1. After your PR is approved and merged to staging, the CI/CD pipeline will:
   - Run tests
   - Deploy to the staging environment

2. Test your changes in the staging environment

### Promoting to Production

1. Use the "Promote to Main" GitHub Action workflow to:
   - Merge staging into main
   - Deploy to production

## CI/CD Workflows

This repository includes several GitHub Actions workflows:

### `staging-cd.yml`
- Triggered when changes are pushed to the staging branch
- Deploys to the staging environment

### `promote-to-main.yml`
- Manually triggered to promote changes from staging to main
- Merges staging into main and deploys to production

### `cd.yml`
- Legacy direct deployment to production (manual only, not recommended)

### `sync-branches.yml`
- Can be used to keep branches in sync
- Creates PRs to keep development in sync with staging, and staging in sync with main

## Setting Up Branch Protection (GitHub Admin)

To fully implement this strategy, a repository admin should set up branch protection rules in GitHub:

1. Go to repository Settings > Branches > Branch protection rules
2. Add rule for the main branch:
   - Check "Require a pull request before merging"
   - Check "Require approvals" (suggest at least 1)
   - Check "Dismiss stale pull request approvals"
   - Check "Require status checks to pass before merging"
   - Add the CI workflow status check as required
   - Check "Require branches to be up to date before merging"
   - Check "Restrict who can push to matching branches"
3. Add similar rules for the staging branch (can be less restrictive)