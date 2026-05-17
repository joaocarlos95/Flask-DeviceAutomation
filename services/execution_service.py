from nornir.core.filter import F


def build_nornir_target_filter(selected_groups: list[str], selected_devices: list[str]):
    """Create Nornir filter expression from selected groups and device names."""
    nornir_target_filter = None
    for group in selected_groups:
        group_filter = F(groups__contains=group)
        nornir_target_filter = group_filter if nornir_target_filter is None else nornir_target_filter | group_filter

    for device in selected_devices:
        device_filter = F(name=device)
        nornir_target_filter = device_filter if nornir_target_filter is None else nornir_target_filter | device_filter

    return nornir_target_filter
