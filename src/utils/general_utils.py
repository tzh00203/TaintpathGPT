def make_hashable(value):
    """确保值是可哈希的，如果是列表则转换为元组"""
    if isinstance(value, list):
        return tuple(value)
    return value

def remove_duplicates(api_list):
    """去重字典列表"""
    seen = set()
    unique_apis = []
    for api in api_list:
        # 处理字典中的每个值，使其变为可哈希
        api_hashable = {k: make_hashable(v) for k, v in api.items()}
        api_tuple = frozenset(api_hashable.items())  # 使用处理后的字典项
        if api_tuple not in seen:
            seen.add(api_tuple)
            unique_apis.append(api)
    return unique_apis