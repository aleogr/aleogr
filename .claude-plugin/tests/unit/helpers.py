"""Helpers of the unit tests (not a test module: discovery looks for test*.py).

Every plugin has a package named `skills` under its scripts/, so a test never imports
`skills.<module>` by name: two plugins' tests in one run would get the same package.
load_skill() loads a skill's module from its file, under a name of its own.
"""

import importlib.util
import os
import sys

sys.dont_write_bytecode = True

PLUGINS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                        "..", "plugins"))
# aleogr_common is byte-identical in every plugin (test_common checks it): one import.
sys.path.insert(0, os.path.join(PLUGINS, "aleogr", "scripts"))

import aleogr_common  # noqa: E402,F401


def plugin_root(plugin):
    return os.path.join(PLUGINS, plugin)


def load_skill(plugin, skill):
    """The module of `skill` (its name, as in SKILL.md) of `plugin`."""
    mod = aleogr_common.module_name(skill)
    path = os.path.join(PLUGINS, plugin, "scripts", "skills", mod + ".py")
    name = "aleogr_test_%s__%s" % (plugin.replace("-", "_"), mod)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def suite_line():
    """The line of a stand-in command (a `#!/bin/sh` script) that answers `--suite` as
    the plugins' commands of this suite do: call_plugin asks it before its first call to
    a command in a process (aleogr_common.reset_suite_checks forgets the answer)."""
    return '[ "$1" = --suite ] && { echo %s; exit 0; }\n' % aleogr_common.suite_digest()
