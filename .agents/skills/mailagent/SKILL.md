```markdown
# mailagent Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you the core development patterns and conventions used in the `mailagent` Python codebase. You'll learn how to structure files, write imports and exports, understand commit message styles, and follow the project's testing and workflow practices. This guide is designed to help maintain consistency and efficiency when contributing to or extending the `mailagent` project.

## Coding Conventions

### File Naming

- Use **snake_case** for all file names.
  - Example: `email_parser.py`, `mail_utils.py`

### Import Style

- Use **relative imports** within the package.
  - Example:
    ```python
    from .utils import parse_headers
    from .models import Email
    ```

### Export Style

- Use **named exports** (explicitly define what is exported).
  - Example:
    ```python
    __all__ = ['parse_headers', 'Email']
    ```

### Commit Messages

- Freeform style, no strict prefix required.
- Average length: ~78 characters.
- Example:
  ```
  Fix parsing bug when subject line contains non-ASCII characters
  ```

## Workflows

### Adding a New Feature
**Trigger:** When implementing a new capability in the mailagent codebase  
**Command:** `/add-feature`

1. Create a new module using snake_case naming.
2. Use relative imports to reference other modules.
3. Implement the feature with named exports.
4. Write or update tests in a corresponding `*.test.*` file.
5. Commit changes with a clear, descriptive message.

### Fixing a Bug
**Trigger:** When resolving a defect or issue  
**Command:** `/fix-bug`

1. Locate the problematic code.
2. Apply the fix, following code style conventions.
3. Update or add tests to cover the bug scenario.
4. Commit with a message describing the fix.

### Writing Tests
**Trigger:** When adding or updating tests  
**Command:** `/write-test`

1. Create or update a test file matching the `*.test.*` pattern.
2. Write test cases for your feature or bugfix.
3. Ensure tests are clear and isolated.

### Reviewing Code
**Trigger:** When reviewing a pull request or changes  
**Command:** `/review-code`

1. Check that file names use snake_case.
2. Ensure all imports are relative.
3. Verify named exports are used.
4. Confirm tests exist for new or changed code.
5. Review commit messages for clarity.

## Testing Patterns

- Test files follow the `*.test.*` naming pattern (e.g., `email_parser.test.py`).
- Testing framework is **unknown**; check existing test files for structure.
- Place tests alongside or near the modules they verify.
- Example test file name: `mail_utils.test.py`

## Commands

| Command        | Purpose                                      |
|----------------|----------------------------------------------|
| /add-feature   | Start workflow for adding a new feature      |
| /fix-bug       | Start workflow for fixing a bug              |
| /write-test    | Start workflow for writing or updating tests |
| /review-code   | Start workflow for reviewing code            |
```