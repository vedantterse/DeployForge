"""
Turning a failed build log into something a student can act on.

Every signature here came from a real failure. The point of the module is that
"pack exited with code 1" is useless to the person who has to fix it, and the
line that explains why is usually buried hundreds of lines up.
"""

from __future__ import annotations

from app.builder import diagnose

# The failure that prompted this: Paketo installs dependencies into a layer and
# symlinks them into the workspace, and Turbopack refuses to follow a symlink
# out of the project root.
TURBOPACK_LOG = """
    > next build --turbopack
       Creating an optimized production build ...
    FATAL: An unexpected Turbopack error occurred.
    [Error [TurbopackInternalError]: Symlink node_modules is invalid, it points
    out of the filesystem root
    exit status 1
ERROR: failed to build: exit status 1
"""

NO_ENTRYPOINT_LOG = """
======== Output: paketo-buildpacks/node-start@2.7.4 ========
could not find app in /workspace: expected one of server.js | app.js | index.js
err:  paketo-buildpacks/node-start@2.7.4 (1)
"""


def test_the_turbopack_symlink_failure_is_recognized():
    found = diagnose.diagnose(TURBOPACK_LOG)
    assert found is not None
    assert "Turbopack" in found.summary
    # The fix has to be actionable, not a restatement of the error.
    assert "next build" in found.fix


def test_a_missing_entrypoint_is_recognized():
    found = diagnose.diagnose(NO_ENTRYPOINT_LOG)
    assert found is not None
    assert "start" in found.fix


def test_the_node_version_failure_is_recognized():
    found = diagnose.diagnose("node: error while loading shared libraries: libatomic.so.1")
    assert found is not None
    assert "engines" in found.fix


def test_an_unrecognized_failure_returns_nothing():
    """A confident wrong explanation is worse than none."""
    assert diagnose.diagnose("something nobody has seen before") is None


def test_an_empty_log_returns_nothing():
    assert diagnose.diagnose("") is None


def test_explain_keeps_the_original_message_when_nothing_matches():
    assert diagnose.explain("mystery output", "exit status 1") == "exit status 1"


def test_explain_leads_with_the_cause_and_keeps_the_tool_error():
    """The student needs the cause; the raw error must not be hidden."""
    message = diagnose.explain(TURBOPACK_LOG, "pack exited with code 1.")
    assert message.startswith("Next.js could not build")
    assert "pack exited with code 1." in message


def test_only_the_tail_of_a_long_log_is_searched():
    """
    A signature from an earlier, unrelated step is not this build's failure.
    """
    noise = "ordinary build output\n" * 5000
    assert diagnose.diagnose(TURBOPACK_LOG + noise) is None


def test_reading_a_missing_log_is_not_an_error():
    assert diagnose.read_tail("C:/nope/does-not-exist.log") == ""


def test_the_tail_reader_returns_the_end_of_the_file(tmp_path):
    log = tmp_path / "build.log"
    log.write_text("start\n" + "x" * 50_000 + "\nTHE END", encoding="utf-8")
    assert diagnose.read_tail(log).endswith("THE END")


# --- Why a container died ----------------------------------------------------
#
# The failure these came from: a student's app pointed at a MongoDB Atlas
# cluster that no longer exists. The platform said "exit code None".

MONGO_DNS_LOG = """
node:internal/dns/promises:295
    this.reject(new DNSException(err, this.bindingName, this.hostname));
                ^
Error: querySrv ENOTFOUND _mongodb._tcp.cluster0.ttul0wi.mongodb.net
    at QueryReqWrap.onresolve [as oncomplete] (node:internal/dns/promises:295:17) {
  errno: undefined,
  code: 'ENOTFOUND',
  syscall: 'querySrv',
  hostname: '_mongodb._tcp.cluster0.ttul0wi.mongodb.net'
}
Node.js v22.23.2
"""


def test_a_missing_mongo_cluster_is_named_as_such():
    found = diagnose.diagnose_runtime(MONGO_DNS_LOG)
    assert found is not None
    assert "MongoDB" in found.summary
    assert "Atlas" in found.fix


def test_a_refused_connection_is_not_confused_with_a_missing_host():
    found = diagnose.diagnose_runtime(
        "Error: connect ECONNREFUSED 172.18.0.3:5432"
    )
    assert found is not None
    assert "nothing was listening" in found.summary


def test_rejected_credentials_are_named():
    found = diagnose.diagnose_runtime(
        "MongoServerError: bad auth : authentication failed"
    )
    assert found is not None
    assert "rejected" in found.summary


def test_an_unknown_crash_is_not_guessed_at():
    """A confident wrong explanation is worse than none."""
    assert diagnose.diagnose_runtime("Segmentation fault (core dumped)") is None


def test_an_unknown_exit_still_points_at_the_runtime_log():
    message = diagnose.explain_exit("something odd", 137)
    assert "exit code 137" in message
    assert "runtime log" in message


def test_an_unknown_exit_code_is_not_printed_as_none():
    """
    A container whose state could not be read has no exit code. "exit code
    None" reads like the app returned something called None.
    """
    message = diagnose.explain_exit("something odd", None)
    assert "None" not in message


def test_a_recognized_cause_comes_before_the_raw_detail():
    message = diagnose.explain_exit(MONGO_DNS_LOG, None)
    assert message.startswith("Your app could not find its MongoDB cluster")
    assert "exited immediately" in message
