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


def plugin_commands():
    """The command of each plugin of the suite (its folder's name)."""
    return sorted(n for n in os.listdir(PLUGINS)
                  if os.path.isfile(os.path.join(PLUGINS, n, "bin", n)))


def called_commands(*modules):
    """Every other plugin's command that the text of `modules` names: a module constant
    whose value is a command (CLOUD, DB, ...) or the command written as a string. A test
    of an orchestrator checks that its SUITE_COMMANDS holds them all."""
    import re
    names = set(plugin_commands()) - {"aleogr"}
    found = set()
    for module in modules:
        with open(module.__file__, encoding="utf-8") as f:
            text = f.read()
        for word in set(re.findall(r"\b[A-Z][A-Z0-9_]*\b", text)):
            value = getattr(module, word, None)
            if isinstance(value, str) and value in names:
                found.add(value)
        for word in re.findall(r"[\"'](aleogr-[a-z0-9-]+)[\"']", text):
            if word in names:
                found.add(word)
    return found


def suite_stand_ins(folder, commands, other):
    """A stand-in for each of `commands` in `folder`: it logs every run of it in
    <folder>/<command>.log and answers `--suite` with this suite's digest, or, for the
    command `other`, with another one. Returns {command: log path}."""
    logs = {}
    for name in commands:
        digest = "0123456789ab" if name == other else aleogr_common.suite_digest()
        path = os.path.join(folder, name)
        with open(path, "w") as f:
            f.write('#!/bin/sh\necho "$*" >> "%s/%s.log"\n'
                    '[ "$1" = --suite ] && { echo %s; exit 0; }\n'
                    'echo \'{"aleogr-result": 1, "status": "unchanged"}\'\n'
                    % (folder, name, digest))
        os.chmod(path, 0o755)
        logs[name] = os.path.join(folder, name + ".log")
    return logs


def read_log(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return f.read().splitlines()


def run_with_other_suite(plugin, skill_name, module, args, other, declaration=None):
    """Run `module` (an orchestrator of `plugin`) in a real Context, in a scratch folder
    (holding `.aleogr/project.json` when `declaration` is given), with a PATH of only
    stand-ins: one per command of module.SUITE_COMMANDS, the command `other` answering
    `--suite` with another digest, and gcloud, gh, git, go and sleep that record being
    run. Returns (result, {command: its log lines}, the provider commands that ran)."""
    import json
    import shutil
    import tempfile
    folder = tempfile.mkdtemp(prefix="aleogr-suite-")
    cwd = os.path.join(folder, "cwd")
    os.makedirs(os.path.join(cwd, ".aleogr"))
    if declaration is not None:
        with open(os.path.join(cwd, ".aleogr", "project.json"), "w") as f:
            json.dump(declaration, f)
    bins = os.path.join(folder, "bin")
    os.makedirs(bins)
    marks = os.path.join(folder, "ran")
    for tool in ("gcloud", "gh", "git", "go", "sleep"):
        p = os.path.join(bins, tool)
        with open(p, "w") as f:
            f.write('#!/bin/sh\necho "$0 $*" >> "%s"\nexit 3\n' % marks)
        os.chmod(p, 0o755)
    logs = suite_stand_ins(bins, module.SUITE_COMMANDS, other)
    old_path, old_cwd = os.environ["PATH"], os.getcwd()
    os.environ["PATH"] = bins
    aleogr_common.reset_suite_checks()
    try:
        os.chdir(cwd)
        ctx = aleogr_common.Context(plugin, plugin_root(plugin), skill_name, module,
                                    getattr(module, "DEFAULT_MODE", "plan"), dict(args))
        result, _code, _why = aleogr_common.run_skill(module, dict(args), ctx)
        ran = read_log(marks)
        return result, dict((k, read_log(v)) for k, v in logs.items()), ran
    finally:
        os.chdir(old_cwd)
        os.environ["PATH"] = old_path
        aleogr_common.reset_suite_checks()
        shutil.rmtree(folder, ignore_errors=True)
