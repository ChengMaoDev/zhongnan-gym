from zhongnan_tray.toggle import Toggle


def test_repeated_tray_click_opens_closes_then_opens() -> None:
    toggle = Toggle()
    assert toggle.should_open(False, 1)
    assert not toggle.should_open(True, 2)
    toggle.hidden(True, 2)
    assert toggle.should_open(False, 3)


def test_outside_dismissal_before_tray_release_does_not_reopen_menu() -> None:
    toggle = Toggle()
    assert toggle.should_open(False, 1)
    toggle.hidden(True, 2)
    assert not toggle.should_open(False, 2.05)
    assert toggle.should_open(False, 3)


def test_click_elsewhere_does_not_suppress_the_next_tray_click() -> None:
    toggle = Toggle()
    toggle.hidden(False, 2)
    assert toggle.should_open(False, 2.05)
