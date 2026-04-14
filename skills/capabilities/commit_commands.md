# Commit Commands

## When Active
When creating git commits, pushing branches, or opening pull requests.

## Instructions
- **Commit**: check `git status`, `git diff HEAD`, current branch, recent commits for context
- Write a concise, descriptive commit message based on the actual changes
- Stage relevant files and commit in a single action
- **Commit + Push + PR workflow**:
  - Create a new branch if on main
  - Create commit with appropriate message
  - Push branch to origin
  - Create PR using `gh pr create`
  - Execute all steps in one pass
- **Clean gone branches**: remove local branches whose remote tracking branch is deleted
- Never force-push without explicit user request
- Follow conventional commit style if the project uses it
