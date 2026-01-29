# Includes work from:
#
# The MIT License
#
# Copyright (c) 2010 Meme Dough
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# Copied from pytest-cov 6.3.0's https://github.com/pytest-dev/pytest-cov/blob/v6.3.0/src/pytest_cov/embed.py
# It was removed to rely on coverage.py's patching of subprocess, etc commands in Python, but because we have
# a Go command in the middle, that doesn't work for us and we go ahead and vendor in and call the embed code
# ourselves.

"""Activate coverage at python startup if appropriate.

The python site initialisation will ensure that anything we import
will be removed and not visible at the end of python startup.  However
we minimise all work by putting these init actions in this separate
module and only importing what is needed when needed.

For normal python startup when coverage should not be activated the pth
file checks a single env var and does not import or call the init fn
here.

For python startup when an ancestor process has set the env indicating
that code coverage is being collected we activate coverage based on
info passed via env vars.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import signal

import coverage

_active_cov = None


def init():
    # Only continue if ancestor process has set everything needed in
    # the env.
    global _active_cov  # noqa: PLW0603

    cov_source = os.environ.get("COV_CORE_SOURCE")
    cov_config = os.environ.get("COV_CORE_CONFIG")
    cov_datafile = os.environ.get("COV_CORE_DATAFILE")
    cov_branch = True if os.environ.get("COV_CORE_BRANCH") == "enabled" else None
    cov_context = os.environ.get("COV_CORE_CONTEXT")

    if cov_datafile:
        assert cov_source is not None
        if _active_cov:
            cleanup()

        # Determine all source roots.
        cov_source = None if cov_source in os.pathsep else cov_source.split(os.pathsep)
        if cov_config == os.pathsep:
            cov_config = True

        # Activate coverage for this process.
        cov = _active_cov = coverage.Coverage(
            source=cov_source,
            branch=cov_branch,
            data_suffix=True,
            config_file=cov_config or False,
            auto_data=True,
            data_file=cov_datafile,
        )
        cov.load()
        cov.start()
        if cov_context:
            cov.switch_context(cov_context)
        cov._warn_no_data = False
        cov._warn_unimported_source = False
        cov._warn_preimported_source = False
        return cov
    return None


def _cleanup(cov):
    if cov is not None:
        cov.stop()
        cov.save()
        cov._auto_save = False  # prevent autosaving from cov._atexit in case the interpreter lacks atexit.unregister
        with contextlib.suppress(Exception):
            atexit.unregister(cov._atexit)


def cleanup():
    global _active_cov  # noqa: PLW0603
    global _cleanup_in_progress  # noqa: PLW0603
    global _pending_signal  # noqa: PLW0603

    _cleanup_in_progress = True
    _cleanup(_active_cov)
    _active_cov = None
    _cleanup_in_progress = False
    if _pending_signal:
        pending_signal = _pending_signal
        _pending_signal = None
        _signal_cleanup_handler(*pending_signal)


_previous_handlers = {}
_pending_signal = None
_cleanup_in_progress = False


def _signal_cleanup_handler(signum, frame):
    global _pending_signal  # noqa: PLW0603
    if _cleanup_in_progress:
        _pending_signal = signum, frame
        return
    cleanup()
    _previous_handler = _previous_handlers.get(signum)
    if _previous_handler == signal.SIG_IGN:
        return
    if _previous_handler and _previous_handler is not _signal_cleanup_handler:
        _previous_handler(signum, frame)
    elif signum == signal.SIGTERM:
        os._exit(128 + signum)
    elif signum == signal.SIGINT:
        raise KeyboardInterrupt


def cleanup_on_signal(signum):
    previous = signal.getsignal(signum)
    if previous is not _signal_cleanup_handler:
        _previous_handlers[signum] = previous
        signal.signal(signum, _signal_cleanup_handler)


def cleanup_on_sigterm():
    cleanup_on_signal(signal.SIGTERM)


init()
