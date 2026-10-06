from argparse import Namespace

from nizam.workers.segment import unmanaged_full_replay


def args(*, all=True, redo=True, dry_run=False):
    return Namespace(all=all, redo=redo, dry_run=dry_run)


def test_raw_full_write_replay_is_refused(monkeypatch):
    monkeypatch.delenv("NIZAM_MANAGED_FULL_REPLAY", raising=False)
    assert unmanaged_full_replay(args())


def test_managed_full_write_replay_is_allowed(monkeypatch):
    monkeypatch.setenv("NIZAM_MANAGED_FULL_REPLAY", "1")
    assert not unmanaged_full_replay(args())


def test_dry_and_bounded_replays_do_not_need_wrapper(monkeypatch):
    monkeypatch.delenv("NIZAM_MANAGED_FULL_REPLAY", raising=False)
    assert not unmanaged_full_replay(args(dry_run=True))
    assert not unmanaged_full_replay(args(all=False))
    assert not unmanaged_full_replay(args(redo=False))
