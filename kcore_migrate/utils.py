from typing import List
import importlib

def collect_attr_from_applications(packages:List[str],file_name:str,attr:str):
    holder = []
    for app in packages:
        mod = None
        try:
            print("trying to import",f'{app}.{file_name}')
            mod = importlib.import_module(f'{app}.{file_name}')
        except ImportError:
            print("unable to import",f'{app}.{file_name}')
        else:
            mod_attr = getattr(mod,attr)
            holder.append(mod_attr)
    return holder