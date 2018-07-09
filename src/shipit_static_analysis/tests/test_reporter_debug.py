# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import json
import os.path


def test_publication(tmpdir, mock_issues):
    '''
    Test debug publication and report analysis
    '''
    from shipit_static_analysis.report.debug import DebugReporter
    from shipit_static_analysis.revisions import MozReviewRevision

    report_dir = str(tmpdir.mkdir('public').realpath())
    report_path = os.path.join(report_dir, 'report.json')
    assert not os.path.exists(report_path)

    r = DebugReporter(report_dir)
    mrev = MozReviewRevision('12345', 'abcdef', '1')
    r.publish(mock_issues, mrev)

    assert os.path.exists(report_path)
    with open(report_path) as f:
        report = json.load(f)

    assert 'issues' in report
    assert report['issues'] == [{'nb': 0}, {'nb': 1}, {'nb': 2}, {'nb': 3}, {'nb': 4}]

    assert 'revision' in report
    assert report['revision'] == {
        'source': 'mozreview',
        'rev': 'abcdef',
        'review_request': 12345,
        'diffset': 1,
        'has_clang_files': False,
        'url': 'https://reviewboard.mozilla.org/r/12345/'
    }

    assert 'time' in report
    assert isinstance(report['time'], float)
