from pathlib import Path
from typing import Union

def get_files(path: Union[str, Path], extension='.wav'):
    """
    获取path路径下以.wav 结尾的文件
    Args:
        path: 存放文件的路径
        extension: 后缀
    Returns:
    """
    if isinstance(path, str): path = Path(path).expanduser().resolve() # 获取绝对路径
    return list(path.rglob(f'*{extension}'))
