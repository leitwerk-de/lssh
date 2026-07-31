import unittest
from unittest import mock

from lssh import config_validation


class ConfigValidationTests(unittest.TestCase):
    def test_invalid_hostname_reports_error_instead_of_syntax_failure(self):
        content = "Host invalid!name\n    User admin\n"
        errors, result = config_validation.transform_config(content, [], None)
        self.assertIsNone(result)
        self.assertTrue(any("invalid characters" in error for error in errors))

    def test_malformed_remote_command_uses_argument_for_suggestion(self):
        content = 'Host example\n    RemoteCommand "unterminated\n'
        errors, result = config_validation.transform_config(content, [], None)
        self.assertIsNone(result)
        self.assertTrue(any("suggested replacement" in error for error in errors))

    def test_valid_configuration_is_passed_to_ssh_validation(self):
        context = []

        def accept(_content, validation_context):
            context.append(validation_context)

        with mock.patch.object(config_validation, "ssh_check_validity", accept):
            errors, result = config_validation.transform_config(
                "Host example\n    HostName example.org\n", [], None
            )
        self.assertEqual(errors, [])
        self.assertIsNotNone(result)
        self.assertEqual(len(context), 1)


if __name__ == "__main__":
    unittest.main()
