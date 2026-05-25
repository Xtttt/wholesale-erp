# PythonAnywhere WSGI 配置
import sys
import os

# 项目路径
path = '/home/xttttt/wholesale-erp'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

from app import app as application
