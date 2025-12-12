#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import requests
import psutil
from git import Repo
from git import RemoteProgress
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.tree import Tree
from rich.panel import Panel
from rich.table import Table

# 配置OpenRouter API
OPENROUTER_CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "model": "qwen/qwen3-vl-8b-instruct",
    "api_key": "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"
}

console = Console()

class DownloadProgressBar(RemoteProgress):
    """自定义Git下载进度条"""
    def __init__(self):
        super().__init__()
        self.progress = Progress(
            TextColumn("[bold blue]下载进度: {task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            console=console
        )
        self.task_id = self.progress.add_task("克隆仓库", total=100)
        self.progress.start()
    
    def update(self, op_code, cur_count, max_count=None, message=''):
        if max_count:
            percent = (cur_count / max_count) * 100
            self.progress.update(self.task_id, completed=percent)
    
    def finish(self):
        self.progress.stop()

def get_user_input():
    """获取用户输入的项目URL，默认使用dify项目"""
    default_repo = "https://gitee.com/dify_ai/dify.git"
    repo_url = Prompt.ask(
        "请输入要安装的开源项目Git URL",
        default=default_repo
    )
    return repo_url

def confirm_download(repo_url):
    """确认是否下载"""
    return Confirm.ask(f"确认要下载项目 [bold cyan]{repo_url}[/bold cyan] 吗？")

def download_repo(repo_url):
    """下载Git仓库，显示进度条"""
    # 从URL中提取项目名称
    repo_name = repo_url.split('/')[-1].replace('.git', '')
    
    # 检查目录是否已存在
    if os.path.exists(repo_name):
        console.print(f"\n[bold yellow]目录 {repo_name} 已存在，跳过下载[/bold yellow]")
        return repo_name
    
    console.print(f"\n[bold green]开始下载项目: {repo_name}[/bold green]")
    
    try:
        # 初始化进度条
        progress_bar = DownloadProgressBar()
        
        # 克隆仓库
        Repo.clone_from(repo_url, repo_name, progress=progress_bar)
        
        # 完成进度条
        progress_bar.finish()
        
        console.print(f"[bold green]✓ 项目下载完成：{repo_name}[/bold green]")
        return repo_name
    except Exception as e:
        console.print(f"[bold red]✗ 下载失败：{e}[/bold red]")
        sys.exit(1)

def get_directory_structure(directory, max_depth=2):
    """获取目录结构，限制最大深度"""
    def _get_structure(directory, tree, current_depth):
        if current_depth > max_depth:
            return
        
        # 获取目录内容并排序
        items = sorted(os.listdir(directory))
        
        # 限制每层目录最多显示10个项目
        max_items_per_level = 10
        items = items[:max_items_per_level]
        
        for item in items:
            # 跳过隐藏文件和目录
            if item.startswith('.'):
                continue
            
            item_path = os.path.join(directory, item)
            
            if os.path.isdir(item_path):
                sub_tree = tree.add(f"[bold blue]{item}/[/bold blue]")
                _get_structure(item_path, sub_tree, current_depth + 1)
            else:
                tree.add(f"[bold white]{item}[/bold white]")
        
        # 如果有更多项目，显示省略号
        if len(os.listdir(directory)) > max_items_per_level:
            tree.add(f"[bold yellow]... (显示前 {max_items_per_level} 个项目)[/bold yellow]")
    
    root_tree = Tree(f"[bold green]{directory}/[/bold green]")
    _get_structure(directory, root_tree, 0)
    return root_tree

def call_openrouter_api(prompt):
    """调用OpenRouter API"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_CONFIG['api_key']}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": OPENROUTER_CONFIG["model"],
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{OPENROUTER_CONFIG['base_url']}/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        console.print(f"[bold red]✗ API调用失败：{e}[/bold red]")
        return ""

def analyze_directory_structure(repo_name):
    """分析目录结构"""
    console.print(f"\n[bold yellow]正在分析项目目录结构...[/bold yellow]")
    
    # 获取目录结构文本（仅一级目录）
    structure_text = f"{repo_name}/\n"
    items = sorted(os.listdir(repo_name))
    
    for i, item in enumerate(items):
        if item.startswith('.'):
            continue
        
        item_path = os.path.join(repo_name, item)
        is_last = i == len(items) - 1
        current_prefix = "└── " if is_last else "├── "
        
        if os.path.isdir(item_path):
            structure_text += f"{current_prefix}{item}/\n"
        else:
            structure_text += f"{current_prefix}{item}\n"
    
    # 调用大模型分析目录结构
    prompt = f"请分析以下项目的目录结构，简要描述该项目的类型、主要功能模块和技术栈：\n\n{structure_text}"
    analysis_result = call_openrouter_api(prompt)
    
    console.print("\n[bold green]目录结构分析结果：[/bold green]")
    console.print(Panel(analysis_result, expand=False))
    
    return analysis_result

def get_readme_content(repo_name):
    """获取README.md内容"""
    readme_path = os.path.join(repo_name, "README.md")
    
    if not os.path.exists(readme_path):
        console.print(f"[bold yellow]✗ 未找到README.md文件，尝试查找其他README文件...[/bold yellow]")
        
        # 尝试查找其他README文件
        for file in os.listdir(repo_name):
            if file.lower().startswith("readme"):
                readme_path = os.path.join(repo_name, file)
                console.print(f"[bold green]✓ 找到README文件：{file}[/bold green]")
                break
        else:
            console.print(f"[bold red]✗ 未找到任何README文件[/bold red]")
            return ""
    
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as e:
        console.print(f"[bold red]✗ 读取README文件失败：{e}[/bold red]")
        return ""

def generate_install_commands(repo_name):
    """根据README.md生成安装命令"""
    console.print(f"\n[bold yellow]正在分析README.md，生成安装命令...[/bold yellow]")
    
    readme_content = get_readme_content(repo_name)
    
    if not readme_content:
        return ""
    
    # 调用大模型生成安装命令
    prompt = f"请根据以下README.md内容，提取并生成该项目的安装命令。请仅返回安装命令，不要包含其他说明文字：\n\n{readme_content}"
    install_commands = call_openrouter_api(prompt)
    
    console.print("\n[bold green]生成的安装命令：[/bold green]")
    console.print(Panel(install_commands, expand=False))
    
    return install_commands

def execute_commands(repo_name, commands):
    """执行安装命令"""
    console.print(f"\n[bold yellow]开始执行安装命令...[/bold yellow]")
    
    # 将命令按行分割
    command_list = commands.strip().split('\n')
    
    # 初始工作目录为当前脚本目录
    current_dir = os.getcwd()
    
    for cmd in command_list:
        cmd = cmd.strip()
        if not cmd:
            continue
        
        console.print(f"\n[bold blue]执行命令：[/bold blue]{cmd}")
        
        try:
            # 处理cd命令，更新当前工作目录
            if cmd.startswith('cd '):
                # 提取目标目录
                target_dir = cmd[3:].strip()
                # 解析目标目录
                new_dir = os.path.abspath(os.path.join(current_dir, target_dir))
                # 检查目录是否存在
                if os.path.exists(new_dir) and os.path.isdir(new_dir):
                    current_dir = new_dir
                    console.print(f"[bold green]✓ 切换目录成功：{current_dir}[/bold green]")
                else:
                    console.print(f"[bold red]✗ 切换目录失败：目录不存在 {new_dir}[/bold red]")
                continue
            
            # 执行其他命令
            result = subprocess.run(
                cmd,
                cwd=current_dir,
                shell=True,
                capture_output=True,
                text=True
            )
            
            # 输出命令结果
            if result.stdout:
                console.print(f"[bold green]输出：[/bold green]\n{result.stdout}")
            if result.stderr:
                console.print(f"[bold red]错误：[/bold red]\n{result.stderr}")
            
            # 特殊处理docker compose up -d命令，考虑到init容器会正常退出
            if cmd == "docker compose up -d":
                # 对于docker compose up -d，即使有些服务是Exited状态（如init容器），只要主要服务运行，就视为成功
                # 检查命令的实际返回码，如果返回码为0，直接视为成功
                if result.returncode == 0:
                    console.print(f"[bold green]✓ 命令执行成功：docker compose服务已启动[/bold green]")
                else:
                    # 如果返回码非0，检查是否有容器正在运行，可能是因为某些init容器退出导致的返回码异常
                    check_result = subprocess.run(
                        "docker compose ps",
                        cwd=current_dir,
                        shell=True,
                        capture_output=True,
                        text=True
                    )
                    if "Running" in check_result.stdout:
                        console.print(f"[bold green]✓ 命令执行成功：docker compose服务已启动[/bold green]")
                    else:
                        console.print(f"[bold red]✗ 命令执行失败，返回码：{result.returncode}[/bold red]")
            elif result.returncode != 0:
                console.print(f"[bold red]✗ 命令执行失败，返回码：{result.returncode}[/bold red]")
            else:
                console.print(f"[bold green]✓ 命令执行成功[/bold green]")
        except Exception as e:
            console.print(f"[bold red]✗ 命令执行出错：{e}[/bold red]")

def get_system_info():
    """获取并展示系统信息"""
    console.print(f"\n[bold yellow]正在获取系统信息...[/bold yellow]")
    
    # 创建系统信息表格
    table = Table(title="系统信息", expand=False)
    table.add_column("项目", justify="right", style="cyan")
    table.add_column("信息", style="magenta")
    
    # CPU信息
    cpu_count = psutil.cpu_count(logical=True)
    cpu_percent = psutil.cpu_percent(interval=1)
    table.add_row("CPU核心数", f"{cpu_count}核")
    table.add_row("CPU使用率", f"{cpu_percent:.1f}%")
    
    # 内存信息
    mem = psutil.virtual_memory()
    mem_total = mem.total / (1024 ** 3)
    mem_used = mem.used / (1024 ** 3)
    mem_percent = mem.percent
    table.add_row("内存总量", f"{mem_total:.1f} GB")
    table.add_row("内存使用", f"{mem_used:.1f} GB")
    table.add_row("内存使用率", f"{mem_percent:.1f}%")
    
    # 磁盘信息
    disk = psutil.disk_usage('/')
    disk_total = disk.total / (1024 ** 3)
    disk_used = disk.used / (1024 ** 3)
    disk_percent = disk.percent
    table.add_row("磁盘总量", f"{disk_total:.1f} GB")
    table.add_row("磁盘使用", f"{disk_used:.1f} GB")
    table.add_row("磁盘使用率", f"{disk_percent:.1f}%")
    
    # 网络信息
    net = psutil.net_io_counters()
    net_sent = net.bytes_sent / (1024 ** 2)
    net_recv = net.bytes_recv / (1024 ** 2)
    table.add_row("网络发送", f"{net_sent:.1f} MB")
    table.add_row("网络接收", f"{net_recv:.1f} MB")
    
    # 启动时间
    boot_time = psutil.boot_time()
    import datetime
    boot_str = datetime.datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M:%S")
    table.add_row("系统启动时间", boot_str)
    
    # 显示表格
    console.print(table)
    
    return {
        "cpu_count": cpu_count,
        "cpu_percent": cpu_percent,
        "mem_total": mem_total,
        "mem_used": mem_used,
        "mem_percent": mem_percent,
        "disk_total": disk_total,
        "disk_used": disk_used,
        "disk_percent": disk_percent,
        "net_sent": net_sent,
        "net_recv": net_recv,
        "boot_time": boot_str
    }

def get_python_dependencies():
    """获取并展示当前Python的依赖信息"""
    console.print(f"\n[bold yellow]正在获取Python依赖信息...[/bold yellow]")
    
    try:
        # 使用pip list命令获取依赖信息
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            console.print(f"[bold red]✗ 获取依赖信息失败：{result.stderr}[/bold red]")
            return []
        
        # 解析依赖信息
        lines = result.stdout.strip().split('\n')
        # 跳过表头
        dependencies = []
        for line in lines[2:]:  # 跳过前两行表头
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    dependencies.append((parts[0], parts[1]))
        
        # 显示依赖信息
        table = Table(title="Python依赖信息", expand=False)
        table.add_column("包名", style="cyan")
        table.add_column("版本", style="magenta")
        
        # 限制显示前20个依赖
        max_dependencies = 20
        display_deps = dependencies[:max_dependencies]
        
        for dep_name, dep_version in display_deps:
            table.add_row(dep_name, dep_version)
        
        if len(dependencies) > max_dependencies:
            table.add_row("...", f"... 共 {len(dependencies)} 个依赖")
        
        console.print(table)
        
        return dependencies
    except Exception as e:
        console.print(f"[bold red]✗ 获取依赖信息出错：{e}[/bold red]")
        return []

def main():
    """主程序入口"""
    console.print("[bold blue]=== 开源项目自动安装工具 ===[/bold blue]")
    
    # 1. 获取用户输入
    repo_url = get_user_input()
    
    # 2. 确认是否下载
    if not confirm_download(repo_url):
        console.print("[bold yellow]操作已取消[/bold yellow]")
        sys.exit(0)
    
    # 3. 下载项目
    repo_name = download_repo(repo_url)
    
    # 4. 显示目录结构
    console.print(f"\n[bold green]项目目录结构：[/bold green]")
    directory_tree = get_directory_structure(repo_name)
    console.print(directory_tree)
    
    # 5. 分析目录结构
    analyze_directory_structure(repo_name)
    
    # 6. 获取系统信息
    get_system_info()
    
    # 7. 获取Python依赖信息
    get_python_dependencies()
    
    # 8. 生成安装命令
    install_commands = generate_install_commands(repo_name)
    
    if not install_commands:
        console.print("[bold red]无法生成安装命令，操作已终止[/bold red]")
        sys.exit(1)
    
    # 7. 确认安装命令
    if not Confirm.ask("确认要执行上述安装命令吗？"):
        console.print("[bold yellow]安装已取消[/bold yellow]")
        sys.exit(0)
    
    # 8. 执行安装命令
    execute_commands(repo_name, install_commands)
    
    console.print(f"\n[bold green]=== 安装完成 ===[/bold green]")

if __name__ == "__main__":
    main()