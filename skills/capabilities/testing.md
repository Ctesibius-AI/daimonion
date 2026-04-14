# Testing

## When Active
When planning test strategy, writing tests, or improving test coverage.

## Instructions
- **Test pyramid**: many unit tests, fewer integration tests, minimal e2e tests
- **Unit tests**: test pure logic in isolation; mock external dependencies; fast execution (<1s each)
- **Integration tests**: test component interactions, database queries, API endpoints with real dependencies
- **E2E tests**: test critical user flows only; use Playwright or Cypress for web; keep these minimal and stable
- Name tests descriptively: `test_<function>_<scenario>_<expected_result>` or `it("should <behavior> when <condition>")`
- Follow Arrange-Act-Assert (AAA) pattern in every test
- Test behavior, not implementation — tests should survive refactors
- Cover edge cases: empty inputs, null/undefined, boundary values, error conditions, concurrent access
- Use fixtures and factories for test data; never hardcode database IDs or timestamps
- Mock at the boundary (HTTP, database, filesystem), not internal functions
- Aim for meaningful coverage, not 100% — focus on business logic and error paths
- Run tests in CI on every push; fail the build on test failures
- Keep tests independent and parallelizable — no shared mutable state between tests
- Snapshot tests: use sparingly; they catch unintended changes but are noisy to maintain
