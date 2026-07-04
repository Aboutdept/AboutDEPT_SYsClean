# -*- coding: utf-8 -*-
"""
SysClean - 系统垃圾文件扫描与清理工具
启动入口
"""

import sys
import os

# 确保可以正确导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import SysCleanApp

if __name__ == "__main__":
    app = SysCleanApp()
    app.run()
