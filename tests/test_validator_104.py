import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'plugins' / 'dravux' / 'skills' / 'dravux'
SCRIPTS = SKILL / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import dravux_contract as contract
import dravux_run as run


def template(name):
    return json.loads((SKILL / 'assets' / name).read_text(encoding='utf-8'))


class Validator104Tests(unittest.TestCase):
    def validate_cli(self, envelope, machine=False):
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPTS / 'dravux_run.py'), 'validate', '-']
            + (['--json'] if machine else []),
            input=json.dumps(envelope), capture_output=True, text=True, check=False,
        )

    def test_validate_prints_preflight_path_expectation_and_bounded_repr(self):
        envelope = template('run-envelope-template.json')
        value = 'false\nFORGED\u202e' + 'x' * 100
        envelope['preflight']['capabilities']['screenshots'] = value
        for machine in (False, True):
            with self.subTest(machine=machine):
                result = self.validate_cli(envelope, machine)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                if machine:
                    payload = json.loads(result.stdout)
                    self.assertEqual(set(payload), {'valid', 'exit_code', 'errors'})
                    messages = payload['errors']
                else:
                    messages = result.stderr.splitlines()
                diagnostic = next((line for line in messages if 'preflight.capabilities.screenshots' in line and 'boolean' in line), '')
                self.assertIn('expected', diagnostic)
                self.assertIn('boolean', diagnostic)
                self.assertIn('found ' + repr(value)[:80], diagnostic)
                self.assertNotIn('x' * 81, diagnostic)
                self.assertNotIn('\u202e', diagnostic)
                self.assertNotIn('Traceback', result.stderr)

    def test_validate_all_preflight_errors_have_context(self):
        cases = (
            (None, 'preflight', 'object'),
            ({}, 'preflight', 'required fields'),
            ('bad-enum', 'preflight.target.input_type', 'WEBSITE'),
            ('bad-mode', 'preflight.selected_mode', 'CONTRACT_ONLY'),
            ('bad-list', 'preflight.required_manual_checks[0]', 'non-empty string'),
            ('duplicate-check', 'preflight.required_manual_checks', 'unique'),
            ('exceeds-ceiling', 'preflight.selected_mode', 'must not exceed'),
            ('missing-checks', 'preflight.required_manual_checks', 'keyboard'),
            ('unknown', 'preflight', 'unknown properties'),
            ('unsafe-url', 'preflight.target.location', 'non-global'),
        )
        for case, path, expected in cases:
            with self.subTest(case=case):
                envelope = template('run-envelope-template.json')
                profile = envelope['preflight']
                if case is None or isinstance(case, dict):
                    envelope['preflight'] = case
                elif case == 'bad-enum':
                    profile['target']['input_type'] = 'bogus'
                elif case == 'bad-mode':
                    profile['selected_mode'] = 'bogus'
                elif case == 'bad-list':
                    profile['required_manual_checks'][0] = ''
                elif case == 'duplicate-check':
                    profile['required_manual_checks'].append(profile['required_manual_checks'][0])
                elif case == 'exceeds-ceiling':
                    profile['selected_mode'] = 'INTERACTIVE'
                elif case == 'missing-checks':
                    profile['required_manual_checks'] = []
                elif case == 'unknown':
                    profile['unknown\nforged'] = True
                elif case == 'unsafe-url':
                    profile['target']['location'] = 'http://127.0.0.1/'
                result = self.validate_cli(envelope, True)
                self.assertEqual(result.returncode, 1)
                messages = json.loads(result.stdout)['errors']
                matching = [line for line in messages if path in line and expected in line]
                self.assertTrue(matching, messages)
                self.assertTrue(any('expected' in line and 'found ' in line for line in matching), messages)
                for message in messages:
                    if 'preflight' in message:
                        self.assertIn('expected', message)
                        self.assertIn('found ', message)
                        self.assertNotIn('\n', message)

    def test_validate_preflight_consistency_errors_have_context(self):
        cases = (
            (('report', 'target', 'input_type'), 'PDF', 'preflight.target.input_type'),
            (('report', 'target', 'location'), 'https://elsewhere.example.org/', 'preflight.target.location'),
            (('acquisition', 'requested_location'), 'https://elsewhere.example.org/', 'preflight.target.location'),
            (('preflight', 'required_manual_checks'), sorted(run.WEBSITE_MANUAL_CHECKS) + ['extra'], 'preflight.required_manual_checks'),
            (('report', 'scope', 'manual_checks_completed'), ['keyboard'], 'preflight.capabilities.manual_evidence'),
            (('report', 'evidence_log'), [{'type': 'MANUAL_OBSERVATION', 'description': 'Keyboard observed',
                                        'locator': 'notes.txt', 'manual_check_id': 'keyboard'}],
             'preflight.capabilities.manual_evidence'),
        )
        for path, value, label in cases:
            with self.subTest(path=path):
                envelope = template('run-envelope-template.json')
                destination = envelope
                for key in path[:-1]:
                    destination = destination[key]
                destination[path[-1]] = value
                result = self.validate_cli(envelope, True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                messages = json.loads(result.stdout)['errors']
                self.assertTrue(any(label in line and 'expected' in line and 'found ' in line for line in messages), messages)

    def test_refusal_and_root_suggestion_escape_hostile_home(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            (base / 'SKILL.md').touch()
            hostile_home = str(base / 'home\nFORGED\u202e')
            for strict, root_only in ((True, False), (False, True)):
                with self.subTest(strict=strict):
                    guard = [Path('/')] if root_only else [base]
                    with mock.patch.dict(os.environ, {'HOME': hostile_home}), mock.patch.object(run, 'guarded_roots', return_value=guard):
                        result = run.resolve_output_dir(base, strict=strict)
                    self.assertEqual(result['exit_code'], 5)
                    self.assertFalse(result['created'])
                    self.assertIn(contract._quoted(Path(hostile_home) / run.OUTPUT_DIR_NAME), result['message'])
                    text = io.StringIO()
                    with redirect_stderr(text):
                        run._print_output_dir(result, False)
                    self.assertEqual(text.getvalue().splitlines(), [result['message']])
                    self.assertNotIn('\u202e', text.getvalue())

    def test_hostile_preflight_field_types_keep_diagnostics_and_exit_shape(self):
        paths = [('preflight_version',), ('package_version',), ('surface',), ('target',),
                 ('capabilities',), ('requested_mode',), ('selected_mode',),
                 ('limitation_acknowledged',), ('required_manual_checks',), ('next_action',)]
        paths += [(group, key) for group, keys in (
            ('surface', run.SURFACE_KEYS), ('target', run.TARGET_KEYS),
            ('capabilities', run.CAPABILITY_KEYS),
        ) for key in sorted(keys)]
        for path in paths:
            for value in (None, {}, [], 42):
                with self.subTest(path=path, value=value):
                    envelope = template('run-envelope-template.json')
                    destination = envelope['preflight']
                    for key in path[:-1]:
                        destination = destination[key]
                    destination[path[-1]] = value
                    result = self.validate_cli(envelope, True)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    payload = json.loads(result.stdout)
                    self.assertEqual(set(payload), {'valid', 'exit_code', 'errors'})
                    label = 'preflight.' + '.'.join(path)
                    self.assertTrue(any(label in line and 'expected' in line and 'found ' in line
                                        for line in payload['errors']), payload)
                    self.assertNotIn('safely rejected hostile structure', result.stdout)

    def test_every_marker_type_guards_ancestors_and_refuses_strict_output(self):
        for marker in run.GUARD_MARKERS:
            for kind in ('file', 'directory', 'file-link', 'directory-link', 'dangling-link', 'fifo'):
                with self.subTest(marker=marker, kind=kind), tempfile.TemporaryDirectory() as directory:
                    base = Path(directory).resolve()
                    tree = base / 'tree'
                    nested = tree / 'nested'
                    nested.mkdir(parents=True)
                    path = tree / marker
                    if kind == 'file':
                        path.touch()
                    elif kind == 'directory':
                        path.mkdir()
                    elif kind in ('file-link', 'directory-link', 'dangling-link'):
                        destination = base / 'destination'
                        if kind == 'file-link':
                            destination.touch()
                        elif kind == 'directory-link':
                            destination.mkdir()
                        path.symlink_to(destination, target_is_directory=kind == 'directory-link')
                    else:
                        os.mkfifo(str(path))
                    self.assertIn(tree, run.guarded_roots(nested))
                    result = run.resolve_output_dir(nested, strict=True)
                    self.assertEqual(result['exit_code'], 5, result)
                    self.assertFalse(result['created'])
                    self.assertFalse((nested / run.OUTPUT_DIR_NAME).exists())

    def test_marker_stat_uncertainty_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            original = Path.lstat
            for failure in (PermissionError('denied'), OSError('I/O error')):
                def denied(path):
                    if path == base / 'SKILL.md':
                        raise failure
                    return original(path)
                with self.subTest(failure=failure), mock.patch.object(Path, 'lstat', denied):
                    self.assertIn(base, run.guarded_roots(base))

    def test_control_policy_rejects_visible_mixed_strings_and_names_codepoints(self):
        codepoints = (list(range(0x20)) + list(range(0x7F, 0xA0))
                      + list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A))
                      + [0x061C, 0x200E, 0x200F, 0x2028, 0x2029])
        for point in codepoints:
            with self.subTest(codepoint=hex(point)):
                value = 'visible' + chr(point) + 'text'
                self.assertFalse(contract._is_nonempty_string(value))
                report = template('report-template.json')
                report['target']['name'] = value
                messages = contract.validate_report(report)
                self.assertTrue(any('target.name' in line and 'U+%04X' % point in line for line in messages), messages)
                profile = template('preflight-template.json')
                profile['surface']['product'] = value
                messages = run.validate_preflight(profile)
                self.assertTrue(any('preflight.surface.product' in line and 'U+%04X' % point in line for line in messages), messages)

    def test_controls_in_list_url_and_run_fields_name_the_field(self):
        mutations = (
            (('report', 'scope', 'included', 0), 'report: scope.included[0]'),
            (('report', 'target', 'location'), 'report: target.location'),
            (('preflight', 'required_manual_checks', 0), 'preflight.required_manual_checks[0]'),
            (('acquisition', 'tool'), 'acquisition.tool'),
            (('execution', 'error'), 'execution.error'),
        )
        for path, label in mutations:
            with self.subTest(path=path):
                envelope = template('run-envelope-template.json')
                value = envelope
                for key in path[:-1]:
                    value = value[key]
                value[path[-1]] = 'visible\u202etext'
                self.assertTrue(any(label in line and 'U+202E' in line for line in run.validate_run(envelope)))

    def test_joiners_and_soft_hyphen_remain_allowed_with_visible_text(self):
        for character in ('\u200d', '\u200c', '\u00ad'):
            with self.subTest(character=repr(character)):
                value = 'visible' + character + 'text'
                self.assertTrue(contract._is_nonempty_string(value))
                report = template('report-template.json')
                report['target']['name'] = value
                self.assertEqual(contract.validate_report(report), [])
                envelope = template('run-envelope-template.json')
                envelope['preflight']['surface']['product'] = value
                self.assertEqual(run.validate_run(envelope), [])

    def test_no_dns_resolution_for_website_hosts(self):
        profile = template('preflight-template.json')
        profile['target']['location'] = 'https://public-looking.example.org/'
        with mock.patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS forbidden')), mock.patch.object(socket, 'gethostbyname', side_effect=AssertionError('DNS forbidden')):
            self.assertEqual(run.validate_preflight(profile), [])
            self.assertFalse(run._website_location_problem(profile['target']['location']))


if __name__ == '__main__':
    unittest.main()
