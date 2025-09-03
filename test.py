import os

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
        print_tree(project_path)
    else:
        print("输入的路径不是有效的目录！")