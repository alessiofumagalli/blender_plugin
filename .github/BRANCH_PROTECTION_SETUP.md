# Branch Protection Setup for Main Branch

This document explains how to configure branch protection rules for the `main` branch to ensure all changes go through pull requests with proper approval.

## Required GitHub Repository Settings

To enforce that all pushes to `main` must go through pull requests that you can approve, configure the following branch protection rules:

### Steps to Configure Branch Protection:

1. Go to your repository on GitHub: `https://github.com/alessiofumagalli/blender_plugin`
2. Click on **Settings** (you need admin access)
3. In the left sidebar, click on **Branches** (under "Code and automation")
4. Under "Branch protection rules", click **Add rule** or **Add branch protection rule**
5. Enter `main` as the branch name pattern
6. Configure the following settings:

#### Required Settings:

- ✅ **Require a pull request before merging**
  - ✅ **Require approvals**: Set to at least 1
  - ✅ **Dismiss stale pull request approvals when new commits are pushed** (recommended)
  - ✅ **Require review from Code Owners** (optional but recommended - uses CODEOWNERS file)
  
- ✅ **Require status checks to pass before merging** (optional)
  - Configure any CI/CD workflows you have
  
- ✅ **Require conversation resolution before merging** (optional but recommended)
  
- ✅ **Include administrators** (optional - if checked, these rules apply to repository administrators too)
  
- ✅ **Restrict who can push to matching branches** (optional but recommended)
  - Add yourself (@alessiofumagalli) to the list of people/teams allowed to push
  - Note: This prevents direct pushes even from administrators
  
- ✅ **Allow force pushes**: Leave this **UNCHECKED** (disabled)
  
- ✅ **Allow deletions**: Leave this **UNCHECKED** (disabled)

7. Click **Create** or **Save changes**

## What This Accomplishes:

1. **No Direct Pushes**: No one can push directly to the `main` branch (including you)
2. **Pull Request Required**: All changes must come through a pull request
3. **Approval Required**: Pull requests must be approved before merging
4. **Code Owner Review**: The CODEOWNERS file ensures you (@alessiofumagalli) are automatically requested as a reviewer
5. **Protected History**: Force pushes and branch deletion are prevented

## CODEOWNERS File

The `.github/CODEOWNERS` file in this repository designates you (@alessiofumagalli) as the owner of all files. This means:
- You will be automatically requested as a reviewer on all pull requests
- If "Require review from Code Owners" is enabled, your approval is mandatory

## Workflow After Setup:

1. Create a new branch for changes: `git checkout -b feature-branch`
2. Make your changes and commit them
3. Push the branch: `git push origin feature-branch`
4. Open a pull request on GitHub
5. Review and approve your own PR (or have another reviewer do it if you've added collaborators)
6. Merge the pull request into `main`

## Testing the Protection:

To verify the protection is working:
```bash
git checkout main
echo "test" >> test.txt
git add test.txt
git commit -m "Test direct push"
git push origin main
```

You should receive an error message indicating that the push was rejected due to branch protection rules.

## Additional Resources:

- [GitHub Docs: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Docs: Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
