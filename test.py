import os
import shutil

# 需要复制的文件列表
target_files = {
    "dmh_service.py",
    "spider_service.py",
    "parser_service.py",
    "settings.py",
    "utils.py",
    "connection.py",
    "models.py",
    "asx_repository.py",
    "asx_spider.py",
    "main_window.py",
    "style_sheet.py",
    "infobar.py",
    "signal_bus.py",
    "base_view.py",
    "spider_view.py",
    "parser_view.py",
    "mr_update_view.py",
    "main.py",
    # 特殊情况：带子路径
    os.path.join("utils", "config.py"),
}

# 目标路径
destination = r"C:\Users\alfre\Desktop\tempfile"


def copy_target_files(root_path):
    if not os.path.exists(destination):
        os.makedirs(destination)

    for dirpath, _, filenames in os.walk(root_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)

            # 计算相对路径（用于匹配像 utils/config.py 这种情况）
            rel_path = os.path.relpath(file_path, root_path).replace("\\", "/")

            # 判断是否在目标文件集合中
            if filename in target_files or rel_path in target_files:
                try:
                    print(f"复制: {file_path}")
                    shutil.copy2(file_path, destination)
                except Exception as e:
                    print(f"复制失败: {file_path} -> {e}")


def print_tree(root, prefix=""):
    """递归打印目录结构"""
    items = os.listdir(root)
    items.sort()  # 排序，保证输出有序
    for index, name in enumerate(items):
        path = os.path.join(root, name)
        connector = "└── " if index == len(items) - 1 else "├── "
        print(prefix + connector + name)
        if os.path.isdir(path):
            extension = "    " if index == len(items) - 1 else "│   "
            print_tree(path, prefix + extension)


if __name__ == "__main__":
    project_path = r'C:\Users\alfre\Desktop\DMH_MR_Tool\src\dmh_mr_tool'
    if os.path.isdir(project_path):
        print(project_path)
        copy_target_files(project_path)
    else:
        print("输入的路径不是有效的目录！")
