# -*- coding: utf-8 -*-
import os.path

import pytest

BAD_CPP_SRC = '''#include <demo>
int \tmain(void){
 printf("plop");return 42;
}'''

BAD_CPP_DIFF = '''1,3c1,4
< #include <demo>
< int \tmain(void){
<  printf("plop");return 42;
---
> #include <demo>
> int main(void) {
>   printf("plop");
>   return 42;
'''

BAD_CPP_VALID = '''#include <demo>
int main(void) {
  printf("plop");
  return 42;
}'''

BAD_CPP_TIDY = '''
void assignment() {
  char *a = 0;
  char x = 0;
}

int *ret_ptr() {
  return 0;
}
'''


def test_expanded_macros(mock_stats, test_cpp, mock_revision):
    '''
    Test expanded macros are detected by clang issue
    '''
    from shipit_static_analysis.clang.tidy import ClangTidyIssue
    parts = ('test.cpp', '42', '51', 'error', 'dummy message', 'dummy-check')
    issue = ClangTidyIssue(parts, mock_revision)
    assert issue.is_problem()
    assert issue.line == 42
    assert issue.char == 51
    assert issue.notes == []
    assert issue.is_expanded_macro() is False

    # Add a note starting with "expanded from macro..."
    parts = ('test.cpp', '42', '51', 'note', 'expanded from macro Blah dummy.cpp', 'dummy-check-note')
    issue.notes.append(ClangTidyIssue(parts, mock_revision))
    assert issue.is_expanded_macro() is True

    # Add another note does not change it
    parts = ('test.cpp', '42', '51', 'note', 'This is not an expanded macro', 'dummy-check-note')
    issue.notes.append(ClangTidyIssue(parts, mock_revision))
    assert issue.is_expanded_macro() is True

    # But if we swap them, it does not work anymore
    issue.notes.reverse()
    assert issue.is_expanded_macro() is False


def test_clang_format(mock_config, mock_repository, mock_stats, mock_clang, mock_revision, mock_workflow):
    '''
    Test clang-format runner
    '''
    from shipit_static_analysis.clang.format import ClangFormat, ClangFormatIssue

    # Write badly formatted c file
    bad_file = os.path.join(mock_config.repo_dir, 'bad.cpp')
    with open(bad_file, 'w') as f:
        f.write(BAD_CPP_SRC)

    # Get formatting issues
    cf = ClangFormat()
    mock_revision.files = ['bad.cpp', ]
    mock_revision.lines = {
        'bad.cpp': [1, 2, 3],
    }
    issues = cf.run(mock_revision)

    # Small file, only one issue which group changes
    assert isinstance(issues, list)
    assert len(issues) == 1
    issue = issues[0]
    assert isinstance(issue, ClangFormatIssue)
    assert issue.is_publishable()

    assert issue.path == 'bad.cpp'
    assert issue.line == 1
    assert issue.nb_lines == 3
    assert issue.as_diff() == BAD_CPP_DIFF

    # At the end of the process, original file is patched
    mock_workflow.build_improvement_patch(mock_revision, issues)
    assert open(bad_file).read() == BAD_CPP_VALID

    # Test stats
    mock_stats.flush()
    metrics = mock_stats.get_metrics('issues.clang-format')
    assert len(metrics) == 1
    assert metrics[0][1]

    metrics = mock_stats.get_metrics('issues.clang-format.publishable')
    assert len(metrics) == 1
    assert metrics[0][1]

    metrics = mock_stats.get_metrics('runtime.clang-format.avg')
    assert len(metrics) == 1
    assert metrics[0][1] > 0


def test_clang_tidy(mock_repository, mock_config, mock_clang, mock_stats, mock_revision):
    '''
    Test clang-tidy runner
    '''
    from shipit_static_analysis.clang.tidy import ClangTidy, ClangTidyIssue

    # Init clang tidy runner
    ct = ClangTidy()

    # Write badly formatted c file
    bad_file = os.path.join(mock_config.repo_dir, 'bad.cpp')
    with open(bad_file, 'w') as f:
        f.write(BAD_CPP_TIDY)

    # Get issues found by clang-tidy
    mock_revision.files = ['bad.cpp', ]
    mock_revision.lines = {
        'bad.cpp': range(len(BAD_CPP_TIDY.split('\n'))),
    }
    issues = ct.run(mock_revision)
    assert len(issues) == 2
    assert isinstance(issues[0], ClangTidyIssue)
    assert issues[0].check == 'modernize-use-nullptr'
    assert issues[0].line == 3
    assert isinstance(issues[1], ClangTidyIssue)
    assert issues[1].check == 'modernize-use-nullptr'
    assert issues[1].line == 8

    # Test stats
    mock_stats.flush()
    metrics = mock_stats.get_metrics('issues.clang-tidy')
    assert len(metrics) == 1
    assert metrics[0][1] == 2

    metrics = mock_stats.get_metrics('issues.clang-tidy.publishable')
    assert len(metrics) == 1
    assert metrics[0][1] == 2

    metrics = mock_stats.get_metrics('runtime.clang-tidy.avg')
    assert len(metrics) == 1
    assert metrics[0][1] > 0


def test_clang_tidy_checks(mock_config, mock_repository, mock_clang):
    '''
    Test that all our clang-tidy checks actually exist
    '''
    from shipit_static_analysis.clang.tidy import ClangTidy
    from shipit_static_analysis.config import CONFIG_URL, settings

    # Get the set of all available checks that the local clang-tidy offers
    clang_tidy = ClangTidy(validate_checks=False)

    # Verify that Firefox's clang-tidy configuration actually specifies checks
    assert len(settings.clang_checkers) > 0, \
        'Firefox clang-tidy configuration {} should specify > 0 clang_checkers'.format(CONFIG_URL)

    # Verify that the specified clang-tidy checks actually exist
    missing = clang_tidy.list_missing_checks()
    assert len(missing) == 0, \
        'Missing clang-tidy checks: {}'.format(', '.join(missing))


def test_clang_tidy_parser(mock_config, mock_repository, mock_revision):
    '''
    Test the clang-tidy (or mach static-analysis) parser
    '''
    from shipit_static_analysis.clang.tidy import ClangTidy
    clang_tidy = ClangTidy()

    # Empty Output
    clang_output = 'Nothing.'
    issues = clang_tidy.parse_issues(clang_output, mock_revision)
    assert issues == []

    # No warnings
    clang_output = 'Whatever text.\n0 warnings present.'
    issues = clang_tidy.parse_issues(clang_output, mock_revision)
    assert issues == []

    # One warning, but no header
    clang_output = 'Whatever text.\n1 warnings present.'
    with pytest.raises(Exception):
        clang_tidy.parse_issues(clang_output, mock_revision)

    # One warning, One header
    clang_output = '/path/to/test.cpp:42:39: error: methods annotated with MOZ_NO_DANGLING_ON_TEMPORARIES cannot be && ref-qualified [mozilla-dangling-on-temporary]'  # noqa
    clang_output += '\n1 warnings present.'
    issues = clang_tidy.parse_issues(clang_output, mock_revision)
    assert len(issues) == 1
    assert issues[0].path == '/path/to/test.cpp'
    assert issues[0].line == 42
    assert issues[0].check == 'mozilla-dangling-on-temporary'


def test_as_text(mock_revision):
    '''
    Test text export for ClangTidyIssue
    '''
    from shipit_static_analysis.clang.tidy import ClangTidyIssue
    parts = ('test.cpp', '42', '51', 'error', 'dummy message withUppercaseChars', 'dummy-check')
    issue = ClangTidyIssue(parts, mock_revision)
    issue.body = 'Dummy body withUppercaseChars'

    assert issue.as_text() == 'SHOULD FAIL'


def test_as_markdown(mock_revision):
    '''
    Test markdown generation for ClangTidyIssue
    '''
    from shipit_static_analysis.clang.tidy import ClangTidyIssue
    parts = ('test.cpp', '42', '51', 'error', 'dummy message', 'dummy-check')
    issue = ClangTidyIssue(parts, mock_revision)
    issue.body = 'Dummy body'

    assert issue.as_markdown() == '''
## clang-tidy error

- **Message**: dummy message
- **Location**: test.cpp:42:51
- **In patch**: no
- **Clang check**: dummy-check
- **Publishable check**: no
- **Third Party**: no
- **Expanded Macro**: no
- **Publishable **: no
- **Is new**: no

```
Dummy body
```


'''
