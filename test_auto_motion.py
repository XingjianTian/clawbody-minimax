from reachy_mini_openclaw.auto_motion import choose_auto_motion


def test_choose_auto_motion_maps_question_to_curious() -> None:
    assert choose_auto_motion("你叫什么名字？") == "curious"


def test_choose_auto_motion_maps_positive_reply_to_happy() -> None:
    assert choose_auto_motion("太好了，我很开心！") == "happy"


def test_choose_auto_motion_maps_confusion_to_confused() -> None:
    assert choose_auto_motion("嗯，我不太确定这个问题。") == "confused"


def test_choose_auto_motion_defaults_to_nod() -> None:
    assert choose_auto_motion("我是 Reachy Mini。") == "nod"


if __name__ == "__main__":
    test_choose_auto_motion_maps_question_to_curious()
    test_choose_auto_motion_maps_positive_reply_to_happy()
    test_choose_auto_motion_maps_confusion_to_confused()
    test_choose_auto_motion_defaults_to_nod()
    print("auto motion tests passed")
