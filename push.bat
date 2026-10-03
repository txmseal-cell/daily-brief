@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================================
echo   daily-brief 一键推送脚本
echo ============================================================
echo.

REM 检查是否在 daily-brief 目录
if not exist "fetch.py" (
    echo [错误] 当前目录没有 fetch.py
    echo 请把这个文件放到 daily-brief 文件夹里再双击
    echo 当前目录：%CD%
    pause
    exit /b 1
)

echo [当前目录] %CD%
echo.

REM 检查 git 是否安装
git --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 没装 Git
    echo 请先去 https://git-scm.com/download/win 下载安装 Git for Windows
    echo 安装时选 "Git from the command line and also from 3rd-party software"
    pause
    exit /b 1
)

echo [1/5] 初始化 git...
git init -q
git config user.name "txmseal-cell"
git config user.email "txmseal-cell@users.noreply.github.com"
echo       完成 ✓
echo.

echo [2/5] 添加所有文件（包括 .github 隐藏文件夹）...
git add .
echo       完成 ✓
echo.

echo [3/5] 提交...
git commit -m "init: daily-brief v3" -q
if errorlevel 1 (
    echo [提示] 没有可提交的更改（可能已经提交过）
)
echo       完成 ✓
echo.

echo [4/5] 设置远程仓库...
git remote remove origin 2>nul
git remote add origin https://github.com/txmseal-cell/daily-brief.git
echo       完成 ✓
echo.

echo [5/5] 推送到 GitHub...
echo       接下来会要你输 GitHub Token（不是登录密码）
echo.

set /p TOKEN="请粘贴 GitHub Personal Access Token（gph_开头的）: "

if "%TOKEN%"=="" (
    echo [错误] Token 不能为空
    pause
    exit /b 1
)

git push -u origin main -f
if errorlevel 1 (
    echo.
    echo [失败] 推送失败，常见原因：
    echo 1. Token 错了或没勾选 'repo' 权限
    echo 2. GitHub 仓库还没建好
    echo 3. 网络问题
    echo.
    echo 试试用 GitHub 仓库的 Settings → Personal access tokens 重新生成
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   推送成功！
echo   去 https://github.com/txmseal-cell/daily-brief 检查
echo ============================================================
echo.
pause