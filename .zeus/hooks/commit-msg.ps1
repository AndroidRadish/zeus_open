# commit-msg.ps1 — Zeus Git Commit Message 格式校验 Hook (Windows 版)
# 安装：cp .zeus/hooks/commit-msg.ps1 .git/hooks/commit-msg.ps1
# 然后在 .git/hooks/commit-msg 中调用 PowerShell：
#   powershell.exe -ExecutionPolicy Bypass -File .git/hooks/commit-msg.ps1 $1
# 或直接重命名为 commit-msg 并修改 Git for Windows 的 hook 调用方式

param(
    [string]$CommitMsgFile
)

if (-not $CommitMsgFile) {
    Write-Host "Usage: commit-msg.ps1 <commit-msg-file>"
    exit 1
}

$CommitMsg = Get-Content -Raw -Path $CommitMsgFile

$TASK_PATTERN = '^(feat|fix|docs|chore|test|refactor)\(T-[0-9]{3}\): .+$'
$ZEUS_PATTERN = '^(feat|fix|docs|chore|test|refactor)\(zeus\): .+$'
$MERGE_PATTERN = '^Merge .+'
$INIT_PATTERN = '^(Initial commit|initial commit|init|Init).*$'

if ($CommitMsg -match $TASK_PATTERN) { exit 0 }
if ($CommitMsg -match $ZEUS_PATTERN) { exit 0 }
if ($CommitMsg -match $MERGE_PATTERN) { exit 0 }
if ($CommitMsg -match $INIT_PATTERN) { exit 0 }

Write-Host ""
Write-Host "❌ Zeus Commit 格式不符合规范！"
Write-Host ""
Write-Host "你的提交信息：$CommitMsg"
Write-Host ""
Write-Host "正确格式："
Write-Host "  任务 commit：{type}(T-{NNN}): {描述}"
Write-Host "  系统 commit：{type}(zeus): {描述}"
Write-Host ""
Write-Host "type 可选：feat / fix / docs / chore / test / refactor"
Write-Host ""
Write-Host "示例："
Write-Host "  feat(T-003): implement user registration form"
Write-Host "  fix(T-007): correct login token expiry logic"
Write-Host "  docs(zeus): update prd from auth-design spec"
Write-Host "  chore(zeus): initialize v2 evolution"
Write-Host ""
exit 1
