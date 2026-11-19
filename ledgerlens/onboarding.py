"""UI-independent onboarding state helpers."""


def should_show_welcome(run_count: int, dismissed: bool = False) -> bool:
    return run_count == 0 and not dismissed
