# Branch Protection Setup Guide

## Current Status

**The main branch is currently NOT protected.** This means that anyone with write access can push directly to the main branch without going through a pull request review process.

## Why Protect the Main Branch?

Branch protection helps maintain code quality and prevents accidental or unauthorized changes to your main codebase by:
- Requiring pull requests before merging
- Enabling code reviews
- Running automated tests before merging
- Preventing force pushes and deletions
- Maintaining a clean git history

## How to Enable Branch Protection

To protect the main branch and require all changes to go through pull requests, follow these steps:

### Step 1: Navigate to Repository Settings

1. Go to your repository on GitHub: https://github.com/alessiofumagalli/blender_plugin
2. Click on **Settings** (you need admin access to the repository)
3. In the left sidebar, click on **Branches** (under "Code and automation")

### Step 2: Add Branch Protection Rule

1. Click the **Add branch protection rule** button (or **Add rule** if no rules exist)
2. In the "Branch name pattern" field, enter: `main`

### Step 3: Configure Protection Settings

Select the following options (recommended for requiring pull requests):

#### Required Settings:
- ✅ **Require a pull request before merging**
  - ✅ **Require approvals** (set to at least 1)
  - ✅ **Dismiss stale pull request approvals when new commits are pushed** (optional but recommended)
  
- ✅ **Require status checks to pass before merging** (if you have CI/CD workflows)
  - Select any required status checks from your GitHub Actions workflows

- ✅ **Require conversation resolution before merging** (optional but recommended)

#### Additional Recommended Settings:
- ✅ **Require linear history** - Prevents merge commits and keeps history clean
- ✅ **Do not allow bypassing the above settings** - Applies rules to administrators too
- ✅ **Restrict who can push to matching branches** - Limits direct pushes (optional)

### Step 4: Save Changes

1. Scroll to the bottom of the page
2. Click **Create** or **Save changes**

## Result

Once branch protection is enabled:
- Direct pushes to the main branch will be blocked
- All changes must be made through pull requests from feature branches
- Pull requests must be reviewed and approved before merging
- This ensures code quality and collaboration

## Workflow After Protection

The recommended workflow after enabling branch protection:

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes and commit:**
   ```bash
   git add .
   git commit -m "Add new feature"
   ```

3. **Push the branch to GitHub:**
   ```bash
   git push origin feature/my-new-feature
   ```

4. **Create a Pull Request:**
   - Go to the repository on GitHub
   - Click "Compare & pull request"
   - Fill in the PR description
   - Request reviews from team members

5. **Merge after approval:**
   - Once approved and checks pass, merge the PR
   - The main branch is updated without direct pushes

## Additional Resources

- [GitHub Documentation: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Documentation: Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
